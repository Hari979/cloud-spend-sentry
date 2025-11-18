# 🛡️ CloudSpend Sentry - AWS Cost Optimization Agent

**Track:** Enterprise Agents  
**Built with:** Python, LangGraph, Google Gemini 1.5 Flash, AWS Boto3, Streamlit

## 💡 The Problem
Cloud bills are opaque. DevOps engineers often struggle to answer two basic questions: *"Where is my money going?"* and *"Am I wasting money?"*.
Manually digging through AWS Cost Explorer to find top spenders and cross-referencing that with EC2/EBS consoles to find "zombie" resources (like unattached volumes) takes hours of context switching.

## 🤖 The Solution
**CloudSpend Sentry** is an autonomous AI agent that acts as a 24/7 FinOps engineer. It provides instant visibility and proactive waste detection in a single chat interface.

The agent follows a "Reasoning Loop":
1.  **Analyzes Trends:** Checks daily spending to detect anomalies.
2.  **Breakdown:** Identifies the top 5 most expensive services (e.g., EC2, RDS) to pinpoint budget drains.
3.  **Investigates:** Proactively scans infrastructure for specific waste patterns (unattached EBS, idle IPs).
4.  **Reports ROI:** Calculates the exact dollar value of potential savings.
5.  **Remembers:** Uses persistent memory to track session context across runs.

## 🛠️ Technical Implementation (The "Rule of 3")
This project demonstrates advanced agentic workflows using:

1.  **Multi-Agent Reasoning (LangGraph):**
    * The agent uses a cyclic graph (`Agent` <-> `Tools`) to reason about data. It dynamically decides whether to drill down into specific resources based on the high-level cost data.
2.  **Custom Tools (AWS Boto3):**
    * `get_recent_cost_trends`: Queries daily cost metrics.
    * `get_top_5_spending_services`: Aggregates monthly costs by Service to identify top spenders.
    * `scan_unused_ebs_volumes`: Identifies unattached disks and estimates monthly waste.
    * `scan_unassociated_ips`: Checks for idle static IPs.
3.  **Persistent Memory (SQLite):**
    * Uses `SqliteSaver` to maintain state. If the user asks "What about RDS?" after the initial report, the agent remembers the previous context.

## 📊 Proof of Impact (Real Run)
In a live test on a production AWS account, the agent provided immediate clarity and identified savings:

> **🤖 Agent Report:**
> * **Cost Trends:** Daily costs are consistent (~$120/day).
> * **Top Spenders (Month-to-Date):**
>   1. **Amazon EC2:** $450.20
>   2. **Amazon RDS:** $120.50
>   3. **AWS Lambda:** $15.00
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
4.  Run the UI (Streamlit):
    ```bash
    streamlit run app_ui.py
    ```
    *Or run the CLI version:*
    ```bash
    python main.py
    ```

## 🔮 Future Improvements
* **Auto-Remediation:** Add a "Fix it" button to allow the agent to delete the resources upon user confirmation (Human-in-the-loop).
* **Slack Integration:** Deploy the agent as a Slack bot for daily cost alerts.