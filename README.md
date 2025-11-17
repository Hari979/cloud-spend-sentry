# 🛡️ CloudSpend Sentry - AWS Cost Optimization Agent

**Track:** Enterprise Agents  
**Built with:** Python, LangGraph, Gemini/OpenAI, AWS Boto3

## 💡 The Problem
Cloud bills are complex. DevOps engineers often miss "zombie" resources—like unattached EBS volumes or idle Elastic IPs—that sit unnoticed for months, silently leaking budget. Manually auditing these resources requires context switching between billing dashboards and infrastructure consoles.

## 🤖 The Solution
**CloudSpend Sentry** is an autonomous AI agent that acts as a 24/7 FinOps engineer. It doesn't just read the bill; it actively investigates infrastructure state to find waste.

The agent follows a "Reasoning Loop":
1.  **Analyzes Trends:** Checks the last 7 days of spending for anomalies.
2.  **Investigates:** If spikes are found (or proactively), it scans for unused resources.
3.  **Reports ROI:** Calculates the exact dollar value of the potential savings.
4.  **Remembers:** Uses persistent memory to track session context.

## 🛠️ Technical Implementation (The "Rule of 3")
This project demonstrates advanced agentic workflows using:

1.  **Multi-Agent Reasoning (LangGraph):**
    * The agent uses a cyclic graph (`Agent` <-> `Tools`) to reason about data. It decides *which* tools to run based on the initial cost findings.
2.  **Custom Tools (AWS Boto3):**
    * `get_recent_cost_trends`: Queries AWS Cost Explorer.
    * `scan_unused_ebs_volumes`: Identifies unattached disks and estimates monthly waste.
    * `scan_unassociated_ips`: Checks for idle static IPs.
3.  **Persistent Memory (SQLite):**
    * Uses `SqliteSaver` to maintain state across executions. If the script crashes or is rerun, the agent retains the context of the current investigation session.

## 📊 Proof of Impact (Real Run)
In a live test on a production AWS account, the agent identified immediate savings:

> **🤖 Agent Report:**
> * **Cost Trends:** Daily costs are consistent (~$120/day).
> * **Waste Detected:** Found **9 unused EBS volumes**.
> * **Potential Savings:** **$30.24 / month**.
> * **Recommendation:** Delete identified volumes immediately.

## 🚀 How to Run

### Prerequisites
* Python 3.10+
* AWS Credentials (with `ce:GetCostAndUsage`, `ec2:DescribeVolumes` permissions)
* Google Gemini API Key (or OpenAI Key)

### Installation
1.  Clone the repository:
    ```bash
    git clone [https://github.com/yourusername/cloud-spend-sentry.git](https://github.com/yourusername/cloud-spend-sentry.git)
    cd cloud-spend-sentry
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Configure environment:
    Create a `.env` file:
    ```ini
    GOOGLE_API_KEY=your_key_here
    AWS_ACCESS_KEY_ID=your_aws_key
    AWS_SECRET_ACCESS_KEY=your_aws_secret
    AWS_REGION=us-east-1
    ```
4.  Run the Agent:
    ```bash
    python main.py
    ```

## 🔮 Future Improvements
* **Auto-Remediation:** Add a tool to allow the agent to *delete* the resources upon user confirmation (Human-in-the-loop).
* **Slack Integration:** Deploy the agent as a Slack bot for daily reports.
