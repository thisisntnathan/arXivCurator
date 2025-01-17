#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSSCuratorBot - main.py

This script is the main entry point for the RSSCuratorBot.
It collects and curates RSS feeds based on user preferences.
The agentic workflow requires access to the OpenAI and GitHub APIs.
"""

__author__ = "Nathan Lui"
__copyright__ = "Copyright 2025"
__credits__ = ["Nathan Lui"]
__license__ = "MIT"
__date__ = "2025-01-17"


import argparse
import datetime
import os
import re

import toml
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent  # , InjectedStore
# from langgraph.store.base import BaseStore
# from langgraph.store.memory import InMemoryStore

from tools import (
    get_user_sources,
    read_and_triage,
    read_rss,
    send_email,
    shorten_abstract,
    update_github_target,
    write_paper_entry,
)


def main(args):
    # load user config
    config = {}
    with open(args.config, "r") as f:
        cfg = toml.load(f)
    cfg["thread_id"] = "thread-0"
    # for LG to understand this everything needs to be nested under "configurable"...
    config["configurable"] = dict(cfg)

    # create toolkit
    tools = [
        read_rss,
        shorten_abstract,
        write_paper_entry,
        update_github_target,
        read_and_triage,
        get_user_sources,
        send_email,
    ]
    for tool in tools:
        tool.name = re.sub(r"[^a-zA-Z0-9_-]", "", tool.name.lower().replace(" ", "_"))

    # checkpointing memory (thread persistence not true memory)
    memory = MemorySaver()

    # persistent memory store for agent (#TODO: implement for context expansion?)
    # store = InMemoryStore()

    sm = SystemMessage(
        "You are a helpful reading assistant. Your primary task is to read \
    through rss feeds and summarize articles. Unless the user specifies otherwise produce \
    the output as a markdown formatted list."
    )

    # initialize supervisor agent
    llm = ChatOpenAI(model="gpt-4o-mini")
    agent_executor = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=sm,
        checkpointer=memory,
        # store=store,  # TODO
    )

    # for output file
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S:%f")

    # lfg
    if args.stream:
        events = agent_executor.stream(
            {"messages": [HumanMessage(args.message)]}, config, stream_mode="values"
        )
        for event in events:
            print(event["messages"][-1].pretty_repr())
    else:
        events = agent_executor.invoke(
            {"messages": [HumanMessage(args.message)]},
            config,
        )
        os.makedirs(args.output_dir, exist_ok=True)
        log_file = os.path.join(
            args.output_dir, f"{timestamp}_{events['messages'][0].id}.log"
        )
        with open(log_file, "w") as f:
            for event in events["messages"]:
                print(event.pretty_repr(), file=f)

        response_file = os.path.join(
            args.output_dir, f"{timestamp}_{events['messages'][0].id}.md"
        )
        with open(response_file, "w") as f:
            print(events["messages"][-1].pretty_repr(), file=f)


if __name__ == "__main__":
    # set environment variables
    load_dotenv()

    # parse cli args
    parser = argparse.ArgumentParser(
        description="ArXiv Curator Agent",
        usage="python main.py [options]",
        epilog="Written by Nathan Lui",
        add_help=True,
    )

    parser.add_argument(
        "-m",
        "--message",
        type=str,
        default="Read through my top rss feeds and update reading list with anything interesting.\
        Make sure to find intereting articles, summarize the abstracts, and upload them to the remote file.",
        help="User message to the agent",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="user.toml",
        help="User configuration file",
    )

    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="results",
        help="Output directory for logs and results",
    )

    parser.add_argument(
        "-s",
        "--stream",
        default=False,
        action="store_true",
        help="Stream the output to the console",
    )

    args = parser.parse_args()

    main(args)
