# arXivCurator

A simple multi-agent system made to read arXiv preprint feeds and look for potentially interesting articles. The agent is set up to either write papers to a remote github file (e.g., [a page on a static website](https://thisisntnathan.github.io/memorypalace/readinglist.html)) or send them in an email digest.  

In the absence of explicit instructions, the agent is prompted to:
1. Read through user-supplied RSS feeds for new articles (from the past day)
1. Determine which papers in the feed could be interesting to the user
1. Summarize the abstracts of potentialy interesting papers
1. Write a list of these potentially interesting articles to a remote file or send them as an email


## Environment

The arXivCurator is built on:

- python
- [feedparser](https://feedparser.readthedocs.io/en/latest/index.html)
- [langchain-openai](https://python.langchain.com/docs/introduction/)
- [langgraph](https://langchain-ai.github.io/langgraph/)
- [openai](https://openai.com/api/)
- [pygithub](https://github.com/PyGithub/PyGithub)
- [dotenv](https://saurabh-kumar.com/python-dotenv/)
- [toml](https://toml.io/en/)

It is recommended that you run arXivCurator in a virtual environment. Use the `environment.yml` file to set up a [mamba](https://mamba.readthedocs.io/en/latest/user_guide/mamba.html) environment.  

```bash
conda env create -f environment.yml
```

If you prefer [venv](https://docs.python.org/3/library/venv.html), a `requirements.txt` is also provided.  

```bash
python3 -m venv .arXivCurator_env
source .arXivCurator_env/bin/activate
python3 -m pip install -r requirements.txt
```

### Jupyter Notebook

If you would like to run agent interactively in a jupyter notebook, also install Jupyter Lab with:

```bash
pip install jupyterlab
```


## User Config

Non-private config information to sent to the agent via the `user.toml` file. GitHub information is only necessary if you want to write to a remote file on GitHub (see [below](#write-to-github)).

```toml
[user]
user_id = "thisisntnathan"
application_context = "arXivCurator"
user_rec_bot_ID = "asst..."
top_rss_feeds = ["https://chemrxiv.org/engage/rss/chemrxiv?categoryId=605c72ef153207001f6470ce", "https://chemrxiv.org/engage/rss/chemrxiv?categoryId=605c72ef153207001f6470d1", "https://chemrxiv.org/engage/rss/chemrxiv?categoryId=605c72ef153207001f6470d0", "https://rss.arxiv.org/rss/physics.chem-ph+physics.bio-ph"]

[user.github]
write_repo = "thisisntnathan/memoryplalace"
write_file = "readinglist.md"
app_name = "your-app-name[bot]"  
app_email = "{bot_user_ID}+your-app-name[bot]@users.noreply.github.com"

[user.email]
sender_email = "..."
sender_email_app_pw = "..."
sender_smtp = "..."
recipient_email = "..."
```

## Output Options

There are two primary ways of reading the output:
- Write to a remote file (on GitHub)
- Send an email digest

### Write to GitHub

The agent is capable of writing papers to a file hosted on GitHub. This could be as simple as a markdown document in a private repo or as complex as a page on a static website. This function requires a GitHub applciation. Follow these instructions on [registering a GitHub application](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app). Make sure that your application has a the following repo permissions:  

- Commit statuses (read only)
- Contents (read and write)
- Issues (read and write)
- Metadata (read only)
- Pull requests (read and write)

Make sure that you give the app permission to access the desired repo. Collect the following from the app interface:

- GITHUB_APP_ID: A six digit number found in your app's general settings (n.b. this is not the bot_id from the API link below)
- GITHUB_APP_PRIVATE_KEY: The location of your app's private key .pem file, or the full text of that file as a string.
- GITHUB_REPOSITORY: The name of the Github repository you want your bot to act upon. Must follow the format `{username}/{repo-name}`. Make sure the app has been added to this repository first!
- (Optional): GITHUB_BRANCH: The branch where the bot will make its commits. Defaults to `repo.default_branch`.
- (Optional): GITHUB_BASE_BRANCH: The base branch of your repo upon which PRs will based from. Defaults to `repo.default_branch`.

Finally, to sign your commits from the app (as opposed to your personal account) collect your app's "user ID" (a 9-digit number) using the GitHub API:  

```
https://api.github.com/users/your-app-name[bot]
```

Save these items in `user.toml`:  

```
app_name = "your-app-name[bot]"  
app_email = "{bot_user_ID}+your-app-name[bot]@users.noreply.github.com"
```

### Email Digest

N.b. This will not work if your network admin does not allow you to send emails

To send emails provide details in the user.email section of user.toml. For security purposes, it is recommended you generate an app specific password for arXivCurator.

## API Keys

The agent uses OpenAI large language models to handle human language understanding. It is set up to read the OpenAI API and GitHub application keys/ID using [python-dotenv](https://github.com/theskumar/python-dotenv).  

You can also set these environment variables manually:

```bash
export OPENAI_API_KEY=sk...
export GITHUB_APP_ID=...
export GITHUB_APP_PRIVATE_KEY=...
export GITHUB_REPOSITORY=username/repo_name
export GITHUB_BRANCH=repo.default_branch
export GITHUB_BASE_BRANCH=repo.default_branch
```

## The Preference Bot

Currently, the preference engine is implemented through the OpenAI [Assistants API](https://platform.openai.com/docs/assistants/overview). The preference agent is a [Retrieval-Augmented Generation (RAG)](https://arxiv.org/abs/2005.11401) bot with access to a preference document. This is akin to multi-shot prompting. Currently 300 examples works pretty well, but the bounds of this method are untested (here be dragons). An example of a preference document is given in `example_papers.txt`.

| title | cls |
| --- | ---: |
| Machine Learning for Reaction Performance Prediction in Allylic Substitution Enhanced by Automatic Extraction of a Substrate-Aware Descriptor | 1 |
| How Do Microbial Metabolites Interact with Their Protein Targets? | 0 |
| Estimation of Ligand Binding Free Energy Using Multi-eGO | 0 |
| SynPlanner: An End-to-End Tool for Synthesis Planning | 1 |
| ... |  |
| DeepSMILES: An Adaptation of SMILES for Use in Machine-Learning of Chemical Structures | 1 |


## Known Issues and TODOs

- [x] Agent seems to have lost the ability to publish from multiple feeds?  
    - Issue: Supervisor users multiple threads to read multiple feeds, cross-thread memory is now sketchy  
    - Fix: previously the memory implementation allowed for cross thread memory, put this back  
- [x] Convert memory store ops to config ops
    - In the future we'll use episodic memory to extend the agent's ability to ingest more articles (see below)  
- [x] Email tool setup and test  
    - N.b. This feature may not work depending on your network admin...  
- [x] Jupyter notebook~~/colab~~ implementation  
- [ ] When there are too many interesting papers (~ >50) the supervisor's context is overwhelmed and the agent starts to "forget" things.  
    - Explore using some sort of episodic memory to store interesting papers as we go to avoid context overflow?  


## Ideas/Contributions

If you'd like to contribute to this project feel free to open and Issue or submit a Pull Request