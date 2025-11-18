import boto3
import json
from datetime import datetime, timedelta, timezone
from langchain_core.tools import tool

# --- AWS CLIENT INITIALIZATION ---
# We initialize these globally so they are reused across calls.
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
    """
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': str(start_date),
                'End': str(end_date)
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )

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
def get_top_5_spending_services(target_month: str = None):
    """
    Identifies the top 5 most expensive AWS services.
    Can analyze the current month-to-date OR a specific past month.

    Args:
        target_month (str, optional): Specific month to check (Format: 'YYYY-MM-DD', e.g. '2025-10-01').
                                      If skipped, analyzes the current month-to-date.
    """
    try:
        # Logic to determine the Time Period
        if target_month:
            # Case A: User wants a specific past month
            try:
                start_date = datetime.strptime(target_month, "%Y-%m-%d").date().replace(day=1)
                # Calculate end date (Start of next month)
                end_date = (start_date + timedelta(days=32)).replace(day=1)
            except ValueError:
                return "Error: Date format must be YYYY-MM-DD."
        else:
            # Case B: User wants current trends (Month-to-Date)
            now = datetime.now()
            start_date = now.replace(day=1)
            end_date = now.date()

            # Edge case: If today is the 1st, look at last month to be helpful
            if start_date == end_date:
                start_date = (now.replace(day=1) - timedelta(days=1)).replace(day=1)

        # AWS API Call
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': str(start_date),
                'End': str(end_date)
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {'Type': 'DIMENSION', 'Key': 'SERVICE'}
            ]
        )

        # Process Data
        service_costs = []
        # Handle potential empty results
        if not response['ResultsByTime']:
            return "No data found for this period."

        groups = response['ResultsByTime'][0]['Groups']

        for group in groups:
            service_name = group['Keys'][0]
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            if amount > 0:
                service_costs.append({'Service': service_name, 'CostUSD': amount})

        # Sort by Cost (Descending) and take top 5
        service_costs.sort(key=lambda x: x['CostUSD'], reverse=True)
        top_5 = service_costs[:5]

        # Format for readability
        formatted_result = []
        for item in top_5:
            formatted_result.append({
                "Service": item['Service'],
                "Cost": f"${item['CostUSD']:,.2f}"
            })

        return json.dumps(formatted_result, indent=2)

    except Exception as e:
        return f"Error fetching top spenders: {str(e)}"

@tool
def scan_unused_ebs_volumes():
    """
    Scans AWS for EBS (Elastic Block Store) volumes that are 'Available'
    (not attached to any EC2 instance). These act as 'zombie' resources
    leaking money.
    """
    try:
        response = ec2_client.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )

        unused_volumes = []
        for vol in response['Volumes']:
            # Estimate cost (Rough approx based on gp3 pricing ~0.08 USD/GB/Month)
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
        response = ec2_client.describe_addresses()

        unused_ips = []
        for ip in response['Addresses']:
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


@tool
def scan_idle_instances(cpu_threshold_percent: float = 5.0):
    """
    Scans for running EC2 instances with low CPU usage (default < 5%)
    over the last 7 days. Returns Instance ID, Name, and CPU metrics.
    """
    try:
        # 1. Get all running instances
        instances = ec2_client.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )

        idle_instances = []
        cw_client = boto3.client('cloudwatch')

        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=7)

        for reservation in instances['Reservations']:
            for inst in reservation['Instances']:
                inst_id = inst['InstanceId']

                # --- FIX: Extract the 'Name' Tag ---
                inst_name = "N/A"
                if 'Tags' in inst:
                    for tag in inst['Tags']:
                        if tag['Key'] == 'Name':
                            inst_name = tag['Value']
                            break
                # -----------------------------------

                # 2. Get CPU Utilization
                metrics = cw_client.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': inst_id}],
                    StartTime=start_time,
                    EndTime=now,
                    Period=86400,
                    Statistics=['Average']
                )

                data_points = metrics.get('Datapoints', [])
                if not data_points: continue

                avg_cpu = sum([dp['Average'] for dp in data_points]) / len(data_points)

                # 3. Check threshold
                if avg_cpu < cpu_threshold_percent:
                    idle_instances.append({
                        'Instance': f"{inst_name} ({inst_id})",  # Combined for readability
                        'Type': inst['InstanceType'],
                        'Avg_CPU_7Day': f"{avg_cpu:.2f}%",
                        'Status': "Idle"
                    })

        if not idle_instances:
            return "No idle EC2 instances found."

        # Return full list
        return json.dumps(idle_instances, indent=2)

    except Exception as e:
        return f"Error scanning idle instances: {str(e)}"

@tool
def scan_old_snapshots(days_old: int = 180):
    """
    Scans for EBS snapshots older than 6 months (default) that are NOT
    used by any registered AMI. These are often forgotten backups.
    """
    try:
        # 1. Get all Snapshots owned by self
        snapshots = ec2_client.describe_snapshots(OwnerIds=['self'])['Snapshots']

        # 2. Get all Snapshots currently used by AMIs (to avoid false positives)
        # AWS won't let you delete these anyway, so we filter them out to be helpful.
        images = ec2_client.describe_images(Owners=['self'])['Images']
        active_snapshot_ids = set()
        for img in images:
            for mapping in img.get('BlockDeviceMappings', []):
                if 'Ebs' in mapping and 'SnapshotId' in mapping['Ebs']:
                    active_snapshot_ids.add(mapping['Ebs']['SnapshotId'])

        # 3. Filter for Old & Unused
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        old_snapshots = []

        for snap in snapshots:
            snap_id = snap['SnapshotId']
            snap_date = snap['StartTime']

            # Check age AND ensure it's not actively used by an AMI
            if snap_date < cutoff_date and snap_id not in active_snapshot_ids:
                old_snapshots.append({
                    'SnapshotId': snap_id,
                    'Created': str(snap_date.date()),
                    'SizeGB': snap['VolumeSize'],
                    'Cost': f"${snap['VolumeSize'] * 0.05}/mo"  # Approx standard pricing
                })

        if not old_snapshots:
            return f"No unused snapshots older than {days_old} days found."

        return json.dumps(old_snapshots, indent=2)

    except Exception as e:
        return f"Error scanning snapshots: {str(e)}"


@tool
def compare_monthly_costs(month_1: str = None, month_2: str = None):
    """
    Compares monthly AWS costs.

    Args:
        month_1 (str, optional): The first month to compare (Format: 'YYYY-MM-DD').
        month_2 (str, optional): The second month to compare (Format: 'YYYY-MM-DD').
    """
    try:
        # --- Logic to determine dates ---
        if month_1 and month_2:
            try:
                date_1 = datetime.strptime(month_1, "%Y-%m-%d").date()
                date_2 = datetime.strptime(month_2, "%Y-%m-%d").date()
                if date_1 > date_2: date_1, date_2 = date_2, date_1

                prior_month_start = date_1.replace(day=1)
                last_month_start = date_2.replace(day=1)

                # Calculate end dates (start of next month)
                prior_month_end = (prior_month_start + timedelta(days=32)).replace(day=1)
                last_month_end = (last_month_start + timedelta(days=32)).replace(day=1)

                api_start = prior_month_start
                api_end = last_month_end
            except ValueError:
                return "Error: Dates must be in 'YYYY-MM-DD' format."
        else:
            # Fallback to Auto-Calculation (Last 2 Complete Months)
            today = datetime.now().date()
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month
            last_month_start = (last_month_end - timedelta(days=1)).replace(day=1)
            prior_month_end = last_month_start
            prior_month_start = (prior_month_end - timedelta(days=1)).replace(day=1)
            api_start = prior_month_start
            api_end = last_month_end

        # --- AWS API Call ---
        response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': str(api_start), 'End': str(api_end)},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        # --- Process Data ---
        service_map = {}

        for result in response['ResultsByTime']:
            period_start = result['TimePeriod']['Start']
            # Determine which month bucket this result belongs to
            is_month_2 = period_start == str(last_month_start if not (month_1 and month_2) else date_2)

            # Handle API returning dates slightly differently than requested
            if month_1 and month_2:
                is_month_2 = period_start == str(date_2)
            else:
                is_month_2 = period_start == str(last_month_start)

            for group in result['Groups']:
                service = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])

                if service not in service_map:
                    service_map[service] = {'Month1': 0.0, 'Month2': 0.0}

                if is_month_2:
                    service_map[service]['Month2'] = cost
                else:
                    service_map[service]['Month1'] = cost

        # --- Calculate Grand Totals (THE FIX) ---
        total_m1 = sum(item['Month1'] for item in service_map.values())
        total_m2 = sum(item['Month2'] for item in service_map.values())
        total_diff = total_m2 - total_m1
        total_percent = (total_diff / total_m1 * 100) if total_m1 > 0 else 0.0

        # --- Calculate Service Differences ---
        changes = []
        for service, data in service_map.items():
            m1_cost = data['Month1']
            m2_cost = data['Month2']

            # Filter out tiny costs to keep report clean
            if m1_cost < 1.0 and m2_cost < 1.0: continue

            diff = m2_cost - m1_cost
            percent = (diff / m1_cost * 100) if m1_cost > 0 else 100.0 if m2_cost > 0 else 0.0

            changes.append({
                'Service': service,
                'Period_1': f"${m1_cost:.2f}",
                'Period_2': f"${m2_cost:.2f}",
                'ChangeUSD': diff,
                'ChangePercent': f"{percent:+.1f}%"
            })

        changes.sort(key=lambda x: abs(x['ChangeUSD']), reverse=True)

        # Return Structure with Totals First
        final_report = {
            "Total_Comparison": {
                "Month_1_Total": f"${total_m1:.2f}",
                "Month_2_Total": f"${total_m2:.2f}",
                "Total_Difference": f"${total_diff:.2f}",
                "Total_Percent_Change": f"{total_percent:+.2f}%"
            },
            "Top_Service_Changes": changes[:5]
        }

        return json.dumps(final_report, indent=2)

    except Exception as e:
        return f"Error comparing costs: {str(e)}"


@tool
def get_monthly_cost_report(target_month: str):
    """
    Retrieves a detailed cost report for a specific month, breaking down
    spend by Service and calculating the Grand Total (including Tax).

    Args:
        target_month (str): The month to report on (Format: 'YYYY-MM-DD', e.g., '2025-10-01').
    """
    try:
        # 1. Calculate Start and End Dates
        start_date = datetime.strptime(target_month, "%Y-%m-%d").date().replace(day=1)
        # Calculate the start of the NEXT month to get the full range of the target month
        end_date = (start_date + timedelta(days=32)).replace(day=1)

        # 2. AWS API Call (Group by Service)
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': str(start_date),
                'End': str(end_date)
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        # 3. Process the Data
        services = []
        grand_total = 0.0
        tax_total = 0.0

        # There should only be one time bucket for a monthly request
        for result in response['ResultsByTime']:
            for group in result['Groups']:
                service_name = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])

                grand_total += amount

                # Check if this line item is Tax
                if "Tax" in service_name:
                    tax_total += amount

                # Only add to list if cost is > $0.01 (exclude 0 cost services to save tokens)
                if amount > 0.01:
                    services.append({
                        "Service": service_name,
                        "Cost": amount,
                        "Formatted": f"${amount:,.2f}"
                    })

        # 4. Sort services by cost (Highest first)
        services.sort(key=lambda x: x['Cost'], reverse=True)

        # 5. Prepare Final Output
        report = {
            "Report_Month": start_date.strftime("%B %Y"),
            "Grand_Total": f"${grand_total:,.2f}",
            "Tax_Included": f"${tax_total:,.2f}",
            "Service_Breakdown": services
        }

        return json.dumps(report, indent=2)

    except Exception as e:
        return f"Error generating monthly report: {str(e)}"