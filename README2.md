# AI Recruitment Platform with Band.ai

An AI-powered recruitment ecosystem built on **Band.ai**, consisting of three specialized agents that collaborate to streamline the hiring and job application process.

## Overview

This project provides an end-to-end recruitment workflow using multiple AI agents:

1. **Recruitment Research Agent** – Analyzes resumes, extracts structured candidate profiles, performs job matching, and researches companies and candidates.
2. **Job Hunter Agent** – Searches a curated jobs database and identifies the most relevant opportunities based on skills, experience, or an extracted CV profile.
3. **Cover Letter Writer Agent** – Generates personalized cover letters and recruiter outreach messages tailored to specific job opportunities.

Together, these agents automate candidate analysis, job discovery, and application material generation.

---

# Architecture

```text
Candidate Resume
       │
       ▼
Recruitment Research Agent
       │
       ├── Extract Candidate Profile
       ├── Resume Analysis
       └── Job Matching
       │
       ▼
Job Hunter Agent
       │
       ├── Search Jobs by Skills
       ├── Search Jobs by Experience
       └── Recommend Relevant Opportunities
       │
       ▼
Cover Letter Writer Agent
       │
       ├── Generate Cover Letter
       └── Generate Recruiter Message
       │
       ▼
Application Package
```

---

# Agents

## 1. Recruitment Research Agent

### Purpose

Analyze candidate resumes and extract structured information that can be used throughout the recruitment workflow.

### Capabilities

* Parse resumes pasted directly into chat
* Extract structured candidate profiles
* Analyze skills and experience
* Match resumes against job descriptions
* Identify missing skills
* Generate hiring recommendations
* Read PDF resumes from URLs
* Research candidates and companies

### Input Examples

#### Resume Analysis

```text
Analyze the following resume:

[resume text]
```

#### Job Matching

```text
Match this resume against the following job description:

Resume:
[resume]

Job:
[job description]
```

### Output

```json
{
  "skills": [
    "Python",
    "Machine Learning",
    "SQL"
  ],
  "experience": [...],
  "education": [...],
  "recommendation": "Strong Match"
}
```

---

## 2. Job Hunter Agent

### Purpose

Find and recommend jobs from the internal jobs database.

### Data Source

The agent uses a local SQLite database:

```text
data/jobs.db
```

Table:

```text
staff_am
```

Only active (non-expired) jobs are returned.

### Capabilities

* Search jobs by skills
* Search jobs by keywords
* Match jobs to candidate profiles
* Rank opportunities by relevance
* Return latest active jobs
* Support requests from users and other agents

### Input Examples

#### Search by Skills

```text
Find jobs requiring:

Python
Computer Vision
PyTorch
```

#### Search by Candidate Profile

```text
Find jobs for this candidate:

{
  "skills": [
    "Python",
    "Machine Learning",
    "Computer Vision"
  ]
}
```

### Output Example

```json
[
  {
    "title": "Computer Vision Engineer",
    "company": "ABC Company",
    "match_score": 92
  },
  {
    "title": "AI Research Engineer",
    "company": "XYZ Company",
    "match_score": 88
  }
]
```

---

## 3. Cover Letter Writer Agent

### Purpose

Generate professional job application materials.

### Capabilities

* Create personalized cover letters
* Create recruiter outreach messages
* Tailor content to specific job descriptions
* Highlight relevant skills and achievements
* Generate complete application packages

### Input Example

```text
Candidate Information:

[profile or resume]

Job Description:

[job description]
```

### Outputs

#### Cover Letter

Professional application letter customized to the role.

#### Recruiter Message

Short outreach message for LinkedIn or email.

Example:

```text
Hello,

I recently came across your opening for a Computer Vision Engineer and was excited by the opportunity. With experience in Python, deep learning, and computer vision research, I believe my background aligns well with your team's needs.

I would welcome the opportunity to discuss how I can contribute.

Best regards,
Mohammad
```

---

# Multi-Agent Workflow

## Scenario 1: Candidate Looking for Jobs

### Step 1

Recruitment Research Agent extracts the profile.

```text
Resume
→ Structured Candidate Profile
```

### Step 2

Job Hunter Agent finds matching jobs.

```text
Candidate Profile
→ Top Matching Jobs
```

### Step 3

Cover Letter Writer Agent generates application materials.

```text
Candidate Profile + Selected Job
→ Cover Letter + Recruiter Message
```

---

## Scenario 2: Recruiter Screening Candidates

### Step 1

Recruitment Research Agent analyzes candidate resumes.

### Step 2

Agent matches candidates to job requirements.

### Step 3

Recruiter receives structured recommendations.

---

# Installation

## Clone Repository

```bash
git clone https://github.com/your-repository.git

cd recruitment-platform
```

## Create Environment

```bash
python -m venv env

source env/bin/activate
```

Windows:

```bash
env\Scripts\activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file:

```env
FEATHERLESS_API_KEY=YOUR_KEY

BAND_WS_URL=YOUR_BAND_WS_URL
BAND_REST_URL=YOUR_BAND_REST_URL
```

---

# Running Agents

## Recruitment Research Agent

```bash
python backend\agents\recruitment-research-agent.py
```

---

## Job Hunter Agent

```bash

python backend\agents\job_hunter_agent.py
```

---

## Cover Letter Writer Agent

```bash
python backend\agents\cover-letter-agent.py
```

---

# Example End-to-End Workflow

### User

```text
Analyze my resume and find Computer Vision jobs.
```

### Recruitment Research Agent

```text
Extracted Skills:
- Python
- OpenCV
- PyTorch
- Deep Learning
```

### Job Hunter Agent

```text
Top Matches:
1. Computer Vision Engineer
2. AI Research Engineer
3. Machine Learning Engineer
```

### User

```text
Generate a cover letter for Job #1.
```

### Cover Letter Writer Agent

```text
Professional Cover Letter
+
Recruiter Outreach Message
```

---

# Technology Stack

* Band.ai
* LangGraph
* LangChain
* DeepSeek V4 Pro
* SQLite
* Python
* Pydantic

---

# Benefits

* Automated resume analysis
* Intelligent job recommendations
* Personalized application materials
* Multi-agent collaboration
* Local job database support
* Scalable recruitment workflow
* Reduced manual effort for candidates and recruiters

---

# Future Improvements

* ATS score prediction
* LinkedIn profile analysis
* Interview preparation agent
* Salary estimation agent
* Candidate ranking dashboard
* Automated application tracking
* Email generation and sending
* Multi-database job aggregation

---

# License

MIT License

Feel free to modify and extend the agents to fit your recruitment workflow.
