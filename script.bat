@echo off

start "Cover Letter Agent" cmd /k python backend\agents\cover-letter-agent.py
start "Recruitment Research Agent" cmd /k python backend\agents\recruitment-research-agent.py
start "Job Hunter Agent" cmd /k python backend\agents\job_hunter_agent.py

echo All agents launched.