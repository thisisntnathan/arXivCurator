#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools.py

This file contains various tools and utilities for the arXivCurator agent to use.
"""

__author__ = "Nathan Lui"
__copyright__ = "Copyright 2025"
__credits__ = ["Nathan Lui"]
__license__ = "MIT"
__date__ = "2025-01-17"

import os
import sys
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP, SMTPConnectError
from time import mktime

import feedparser
from github import Auth, GithubIntegration, InputGitAuthor
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

# from langgraph.prebuilt import InjectedStore
# from langgraph.store.base import BaseStore
from openai import OpenAI
from typing_extensions import Annotated


@tool
def get_user_sources(config: RunnableConfig) -> list[str]:
    """Get this user's top rss feeds for reading.
    Only call this tool if the user does not specify a rss feed url in the query
    """
    return config["configurable"]["user"]["top_rss_feeds"]


@tool
def read_rss(url: str, num_articles: int = sys.maxsize) -> list[dict]:
    """This tool will read data from an RSS feed and return articles from the feed
    regardless of potential interest. If a certain number of articles is requested
    the list will return no more than the specified number of articles. By default
    this tool returns all articles in the feed.
    """
    return feedparser.parse(url)["entries"][:num_articles]


@tool
def read_and_triage(
    url: str,
    config: RunnableConfig,
) -> list[dict]:
    """This tool will read data from an RSS feed and return papers from the feed are
    interesting to the user."""
    new_papers = [
        entry
        for entry in feedparser.parse(url)["entries"]
        if date.fromtimestamp(mktime(entry["updated_parsed"]))
        >= date.today() - timedelta(days=1)
    ]
    titles = "\n".join(
        [
            "- " + (paper.get("title").replace("\n", " ").replace(".", ""))
            for paper in new_papers
        ]
    )
    # grab feed title for later
    try:
        feed_title = feedparser.parse(url)["feed"]["title"]
    except KeyError:
        feed_title = url

    # instantiate preference agent
    client = OpenAI()
    evaluator_assistant = client.beta.assistants.retrieve(
        config["configurable"]["user"]["user_rec_bot_id"]
    )
    thread = client.beta.threads.create()
    _ = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"This is a list of papers, determine whether each paper is interesting:\n{titles}",
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=evaluator_assistant.id,
    )

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        res = messages.data[0].content[0].text.value
    else:
        return f"ERROR: {run.status}"

    interesting_titles = []
    for line in res.split("\n"):
        if line.endswith("True"):
            interesting_titles.append(line[2:-6])

    interesting_papers = [
        paper
        for paper in new_papers
        if paper.get("title").replace("\n", " ").replace(".", "") in interesting_titles
    ]

    outs = []
    for paper in interesting_papers:
        entry = {
            "title": paper.get("title").replace("\n", " ").replace(".", ""),
            "abstract": paper.get("summary"),
            "link": paper.get("link"),
            "date": paper.get("updated"),
            "authors": paper.get("authors"),
            "source": feed_title,
        }
        outs.append(entry)

    return outs


@tool
def shorten_abstract(title: str, abstract: str) -> str:
    """This tool uses an llm to summarize a paper from its title and abstract"""
    client = OpenAI()
    messages = [
        {
            "role": "system",
            "content": "Summarize the following paper from its title and abstract. \
            Make sure to highlight any datasets, methods, and results that are mentioned. \
            Keep your summary to fewer than 60 words",
        },
        {
            "role": "user",
            "content": f"The paper title is {title}\nThe abstract is {abstract}",
        },
    ]

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )

    return completion.choices[0].message.content


@tool
def write_paper_entry(
    title: str, link: str, authors: str, summary: str, date: str, source: str
) -> str:
    """This tool writes a nice summary of the paper to add to the reading list.
    Do not call this tool without calling 'shorten_abstract()' first.
    The summary is formatted in Markdown language as an entry in an unnumbered list.
    """
    return (
        f"- [{title}]({link})  \n{authors}  \n*{source}*  \n{date}  \n&ensp;{summary}  "
    )


@tool
def update_github_target(payload: str, config: RunnableConfig) -> str:
    """This tool updates the target file on github with the formatted list entries.
    The input to this tool should be only the formatted list entries without any header.
    """
    with open(os.environ["GITHUB_APP_PRIVATE_KEY"], "r") as file:
        key = file.read()
    gi = GithubIntegration(auth=Auth.AppAuth(os.environ["GITHUB_APP_ID"], key))
    g = gi.get_installations()[0].get_github_for_installation()
    del key

    repo = g.get_repo(config["configurable"]["user"]["github"]["write_repo"])
    file = repo.get_contents(config["configurable"]["user"]["github"]["write_file"])

    page_lines = file.decoded_content.decode("utf-8").split("\n")

    if page_lines[14].startswith(f"## {date.today().strftime('%d %b %Y')}"):
        daily_update = "\n" + payload
        page_lines.insert(15, daily_update)
    else:
        daily_update = f"\n## {date.today().strftime('%d %b %Y')}  \n\n" + payload
        page_lines.insert(13, daily_update)

    page_contents = "\n".join(page_lines)

    commit_msg = f"Curator added papers from {date.today().strftime('%d-%m-%Y')}"

    agent_author = InputGitAuthor(
        config["configurable"]["user"]["github"]["app_name"],
        config["configurable"]["user"]["github"]["app_email"],
    )

    sig = repo.update_file(
        path=file.path,
        content=page_contents,
        message=commit_msg,
        sha=file.sha,
        author=agent_author,
        committer=agent_author,
    )

    try:
        commit_hash = sig["commit"].sha
    except KeyError:
        commit_hash = "COMMIT ERROR: DO NOT TRY AGAIN. SEND AN EMAIL INSTEAD."

    return f"Readinglist Updated!\nTo catch up on the your reading, visit\
    https://thisisntnathan.github.io/memorypalace/readinglist.html\
    \nCommit hash:{commit_hash}"


@tool
def send_email(payload: str, config: RunnableConfig) -> str:
    """This tool sends an email to the user with the daily reading list digest."""
    host = config["configurable"]["user"]["email"]["sender_smtp"]

    try:
        with SMTP(host=host, port=587, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(
                config["configurable"]["user"]["email"]["sender_email"],
                config["configurable"]["user"]["email"]["sender_email_app_pw"],
            )

            msg = MIMEMultipart()
            msg["From"] = (
                f"arXivCurator <{config['configurable']['user']['email']['sender_email']}>"
            )
            msg["To"] = config["configurable"]["user"]["email"]["recipient_email"]
            msg["Subject"] = (
                f"Your Daily Reading List - {date.today().strftime('%d %b %Y')}"
            )
            msg.attach(MIMEText(payload, "plain"))

            s.send_message(msg)
    except TimeoutError as e:
        return f"Email could not be sent. Connection timed out.\n{e}"
    except SMTPConnectError as e:
        return f"Email could not be sent. Connection error.\n{e}"

    return "Email sent successfully!"


#### DEPRECATED MEMORY IMPLEMENTATION
# @tool
# def get_user_sources(
#     config: RunnableConfig, store: Annotated[BaseStore, InjectedStore()]
# ) -> list[str]:
#     """Get this user's top rss feeds for reading.
#     Only call this tool if the user does not specify a rss feed url in the query
#     """
#     user_id = config["user"]["user_id"]
#     application_context = config["user"]["application_context"]
#     namespace = (user_id, application_context)
#     feeds = store.get(namespace, "top_rss_feeds")
#     return list(feeds.value.values())
