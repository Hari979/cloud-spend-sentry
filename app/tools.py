import boto3
import json
from datetime import datetime, timedelta
from langchain_core.tools import tool

# --- AWS CLIENT INITIALIZATION ---
# We initialize these globally so they are reused across calls.
# Ensure your environment has AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION set.
try:
    ce_client = boto3.client('ce')  # Cost Explorer
    ec2_client = boto3.client('ec2')  # EC2 (Compute & Storage)
except Exception as e:
    print(f"Error initializing AWS clients: {e}")
    print("Make sure your .env file is set up correctly with AWS credentials.")


# --- TOOL DEFINITIONS ---

@tool
def get_recent_cost_trends(days: int = 7):
    """
    Fetches daily AWS cost data for the specified number of past days.
    Useful for identifying spending spikes or trends.

    Args:
        days (int): The number of days to look back (default is 7).
    """
    try:
        # AWS Cost Explorer requires dates in 'YYYY-MM-DD' format
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # Cost Explorer API Call
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': str(start_date),
                'End': str(end_date)
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )

        # Parse the complex JSON response into something the LLM can read easily
        costs = []
        for item in response['ResultsByTime']:
            date = item['TimePeriod']['Start']
            amount = float(item['Total']['UnblendedCost']['Amount'])
            costs.append({
                'date': date,
                'cost_usd': round(amount, 2)
            })

        return json.dumps(costs, indent=2)

    except Exception as e:
        return f"Error fetching cost trends: {str(e)}"


@tool
def scan_unused_ebs_volumes():
    """
    Scans AWS for EBS (Elastic Block Store) volumes that are 'Available'
    (not attached to any EC2 instance). These act as 'zombie' resources
    leaking money.
    """
    try:
        # Filter for volumes where status is 'available'
        response = ec2_client.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )

        unused_volumes = []
        for vol in response['Volumes']:
            # Estimate cost (Rough approx based on gp3 pricing ~0.08 USD/GB/Month)
            # This helps the agent prioritize larger wasted volumes
            size_gb = vol['Size']
            est_cost = size_gb * 0.08

            unused_volumes.append({
                'VolumeId': vol['VolumeId'],
                'SizeGB': size_gb,
                'Type': vol['VolumeType'],
                'Created': str(vol['CreateTime'].date()),
                'EstimatedMonthlyWasteUSD': f"${est_cost:.2f}"
            })

        if not unused_volumes:
            return "Great news! No unused EBS volumes found."

        return json.dumps(unused_volumes, indent=2)

    except Exception as e:
        return f"Error scanning EBS volumes: {str(e)}"


@tool
def scan_unassociated_ips():
    """
    Scans AWS for Elastic IPs (EIPs) that are allocated but not associated
    with a running instance. AWS charges for these when they are idle.
    """
    try:
        # Get all addresses
        response = ec2_client.describe_addresses()

        unused_ips = []
        for ip in response['Addresses']:
            # If 'AssociationId' is missing, the IP is sitting idle
            if 'AssociationId' not in ip:
                unused_ips.append({
                    'PublicIp': ip['PublicIp'],
                    'AllocationId': ip['AllocationId'],
                    'Region': ip.get('NetworkBorderGroup', 'unknown')
                })

        if not unused_ips:
            return "No unassociated Elastic IPs found."

        return json.dumps(unused_ips, indent=2)

    except Exception as e:
        return f"Error scanning Elastic IPs: {str(e)}"