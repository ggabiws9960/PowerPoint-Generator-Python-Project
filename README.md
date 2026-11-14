![banner](https://github.com/otahina/PowerPoint-Generator-Python-Project/assets/108225969/bfe8f796-3ffa-4c59-92f5-7624f6f9884f)

[![made-with-python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/otahina/PowerPoint-Generator-Python-Project.git)
[![View My Profile](https://img.shields.io/badge/View-My_Profile-green?logo=GitHub)](https://github.com/otahina)

<img src="https://img.shields.io/github/stars/otahina/PowerPoint-Generator-Python-Project.svg"> <img src="https://img.shields.io/github/forks/otahina/PowerPoint-Generator-Python-Project.svg">

## 이 포크에서 달라진 것 — 구조화 덱 방식 (2026-11)

원본은 GPT-3.5 가 쓴 글을 python-pptx 템플릿의 제목·글머리표 자리에 그대로 채웠다. 이 포크는 생성 핵심을 바꿨다.

1. **Claude 가 장별 구조화 명세(JSON)를 쓴다** — 장마다 유형(표지·목차·섹션·글머리표·카드·숫자 타일·표·두 열·비교·단계·마무리)을 고르고, 구조화 출력(`output_config.format`)으로 형식이 보장된 JSON 을 받는다. `myapp/utils/claude_generate.py`
2. **Node 렌더러가 테마를 입혀 PPTX 를 만든다** — pptxgenjs 로 테마(12색 스킴·글꼴·로고) → 레이아웃(제목 자리·쪽 번호) → 장 유형별 카드·타일·표·차트를 그리고, 테마 색을 파일에 기록해 PowerPoint 의 「디자인 > 색 변형」으로 한 번에 바꿀 수 있게 한다. `renderer/build.js`, 테마 `renderer/themes/*.json`
3. **렌더로 검사한다** — `renderer/preview.ps1`(Windows, PowerPoint) 이 장마다 PNG 를 뽑아 겹침·넘침을 눈으로 본다.

화면은 볼트의 **디자인 3번(Wise)** — 세이지 바탕·흰 카드·라임 버튼·Pretendard 900 제목 — 으로 한글화했다(`myapp/static/CSS/wise.css`, 색은 `--w-` 변수로만). Flask 로그인은 그대로이고, `/generator` 는 JSON 으로 내려받기 링크를 돌려준다. 명세를 직접 써서 `/render` 로 보내면 모델 없이 렌더만 할 수도 있다. 명세 형식은 [docs/SPEC.md](docs/SPEC.md).

```bash
# 1) Node 렌더러
cd renderer && npm install && node build.js examples/sample-ko.json out/sample-ko.pptx --theme climath && cd ..
# 2) Python
python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
copy .env.example .env   # SECRET_KEY, ANTHROPIC_API_KEY 채우기
cd myapp && python flaskapp.py   # http://localhost:5001/generator
```

---

## PowerPoint Generator: Your Gateway to Effortless Presentations 🚀

Dive into the ease of presentation creation with PowerPoint Generator, a smart web application crafted to automate 
PowerPoint presentations! 🌟 
This project is ripe for growth and eager for your contributions. Let's enhance its capability together! 😊

## Demo Highlights 🎬

https://github.com/otahina/PowerPoint-Generator-Python-Project/assets/108225969/82d98c7a-0244-4fed-8f6b-f6c994fd69e3

## Table of Contents 📋

1. [Features](#features)
2. [Inner Structure of the Project](#inner-structure-of-the-project)
3. [How to Use](#how-to-use)
4. [How to Contribute](#how-to-contribute)

## Features 

* **🤖 AI-Driven Content Creation**: Claude writes a structured slide spec (JSON) — one message per slide, slide types chosen per content.
* **😎 Intelligent Slide Generation**: The tool intelligently proposes titles and content for each slide.
* **🎨 Theme-driven rendering**: pptxgenjs renders cards, stat tiles, tables and charts with a 12-color PowerPoint theme (`renderer/themes/*.json`) — recolor the whole deck in PowerPoint afterwards.
* **🙂 User-Friendly Interface**: Clear instructions and an intuitive design make the PowerPoint generation process seamless and straightforward.

## Inner Structure of the project 

If you want to learn how to use the GPT API for creating PowerPoint presentations or understand how the project is 
organized, check out [CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md). 🧐
In this document, I explain the code and the relationships between different parts of the code.

## How to use

If you want to try using this project, here is a step-by-step guide. 
Those who want to contribute to (which is welcome!), please check [How to Contribute](#how-to-contribute)

<details>
<summary>
Step 1: Star The Repo ⭐️
</summary>

Star the repo to start using this project 👍

![star repo](https://docs.github.com/assets/images/help/stars/starring-a-repository.png)

</details>

---

<details>
<summary>
Step 2: Clone It 🐑
</summary>

- **Using Git** 

Open your terminal and run the following command:

```bash
git clone https://github.com/otahina/PowerPoint-Generator-Python-Project.git
```

- **Using Download ZIP**

1. Go to the GitHub page of the repository.
2. Click on the green **Code** button.
3. In the dropdown menu, select **Download ZIP**.

</details>

---
<details>
<summary>
Step 3: Create a Virtual Environment 📟
</summary>

On Windows 🪟
- Open your **Command Prompt** and navigate to your project's directory.
- Run the command line by line.
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```
On macOS and Linux 🐧
- Open your **Terminal** and navigate to your project's directory.
- Run the command line by line.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
</details>

---

<details>
<summary>
Step 4: Setup API Keys 🔑
</summary>

⚠️ This step is very important to make the project work! 
please make sure if you set up everything correctly. 
Instruction ▶️ [Setup the Secret Key and OpenAI Key](set-up-api-keys)

</details>

---

<details>

<summary>
Step 5: Run 🏃‍
</summary>

Navigate to `myapp` directory. Run `flaskapp.py`

```bash
python3 myapp/flaskapp.py
```

</details>

## How to contribute 

Thank you for considering how you can contribute to the project! ✨

<details>
<summary>
Step 1: Star The Repo ⭐️
</summary>

Star the repo to start your contribution ⭐️

![star repo](https://docs.github.com/assets/images/help/stars/starring-a-repository.png)

</details>

---

<details>
<summary>
Step 2: Fork it 🍴
</summary>

On the [GitHub page for this repository](https://github.com/otahina/PowerPoint-Generator-Python-Project.git), click on the Button "**Fork**".

![fork image](https://upload.wikimedia.org/wikipedia/commons/3/38/GitHub_Fork_Button.png)

</details>

---

<details>
<summary>
Step 3: Clone it 🐑
</summary>

- **Method 1:** GitHub Desktop

> ⚠️ **NOTE:** If you're not familiar with Git, using **GitHub Desktop Application** is a better start. If you choose this method, make sure to download it before continuing reading.
>
> ❗❗ Access link to download [**here**](https://desktop.github.com).

- **Method 2:** Git

Clone the **forked repository**. Open terminal (command prompt) and type:

```bash
git clone https://github.com/<your-github-username>/PowerPoint-Generator-Python-Project.git
```

> This makes a local copy of the repository in your machine.
>
> ⚠️ **Replace \<your-github-username\>!**

</details>

---

<details>
<summary>
Step 4: Create your feature branch 🌴
</summary>

Always keep your local copy of the repository updated with the original repository.
Before making any changes and/or in an appropriate interval, follow the following steps:

- **Method 1:** GitHub Desktop

Learn more about how to create new branch [here](https://docs.github.com/en/desktop/contributing-and-collaborating-using-github-desktop/making-changes-in-a-branch/managing-branches#creating-a-branch) and how to fetch and pull origin from/to your local machine [here](https://docs.github.com/en/desktop/contributing-and-collaborating-using-github-desktop/keeping-your-local-repository-in-sync-with-github/syncing-your-branch).

Learn more about how to fetch and pull origin from/to your local machine using **GitHub Desktop** [here](https://docs.github.com/en/desktop/contributing-and-collaborating-using-github-desktop/keeping-your-local-repository-in-sync-with-github/syncing-your-branch).

- **Method 2:** Git

Run the following commands **_carefully_** to update your local repository.

```bash
# If you cloned a while ago, get the latest changes from upstream
git checkout main
git remote add upstream https://github.com/otahina/PowerPoint-Generator-Python-Project.git
git pull upstream main

# Make a feature branch (Always check your current branch is up to date before creating a new branch from it to avoid merge conflicts)
git checkout -b <branch-name>

```

</details>

---
<details>
<summary>
Step 5: Pull Request 🖐️
</summary>

1. Open the GitHub website and find your forked repository.
2. On your fork's GitHub page, click 'New Pull Request'.
3. Ensure the base branch is the original repository's branch you want to merge into(main branch), 
and the compare branch is your feature branch.
4. Click 'Create Pull Request', add a title and a brief description of your changes.

Thank you for your contribution! 
I'll check your pull request. 😀

</details>

---

If you want to learn more about how to contribute, visit [CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Setup the Secret Key and Claude API Key

`.env.example` 을 `.env` 로 복사해 채운다.

```
SECRET_KEY=your_secret_key
ANTHROPIC_API_KEY=your_anthropic_key
CLAUDE_MODEL=claude-opus-5-5
```

**SECRET_KEY**: 🔐 Flask 세션용 임의의 긴 문자열.

**ANTHROPIC_API_KEY**: 🤖 https://platform.claude.com 에서 발급. 명세를 쓰는 모델은 `CLAUDE_MODEL` 로 바꾼다(기본 `claude-opus-5-5`).

Pexels 키는 더 이상 쓰지 않는다(사진 삽입 기능 제거).

## Community Discussions 🗣️
Have a question, idea, or want to contribute? Join us in [Discussions](https://github.com/otahina/PowerPoint-Generator-Python-Project/discussions)!

## Contributors ✨

<img src="https://github.com/otahina.png" width="50" height="50" alt="description">
<a href="https://github.com/otahina">Ota Hina</a>
<img src="https://github.com/gaganmanku96.png" width="50" height="50" alt="description">
<a href="https://github.com/gaganmanku96">Gagandeep Singh</a>


## License 📄

This project is licensed under the terms of the MIT license.




