# Architecture

## Overview

![Architecture](../assets/architecture_pandas.png)


## Storage Layer (Amazon S3)
- The solution uses a single Amazon S3 bucket: `huynm43-mock-project-s3-414061810527-us-east-1-an`.
- Data is organized into the following prefixes:
  - `rcv/` – Raw incoming files.
  - `l0/` – Cleansed and validated data.
  - `l1/` – Business-ready transformed data.
  - `quarantine/` – Invalid files isolated for investigation (rcv - l0).
  - `audit/` – Invalid records (l0 - l1).
  - `ec2-airflow/` – Stores Apache Airflow DAGs.

- Configuration for each table and layer is stored as **YAML files** under:

```text
config/{layer}/{table}.yaml

Examples:
config/rcv/customers.yaml
config/l0/customers.yaml
config/l1/customers.yaml
```


## Component Responsibility
| # | Component | Type | Primary Responsibility |
|---|---|---|---|
| 1 | S3 `ec2-airflow/` | Storage | Stores Apache Airflow DAG source code and supporting Python modules. |
| 2 | S3 `config/` | Storage | Stores YAML configuration files for each layer (`rcv`, `l0`, `l1`) and table-specific processing rules. |
| 3 | S3 Data Lake (`rcv`, `l0`, `l1`, `quarantine`, `audit`) | Storage | Stores raw files, validated datasets, transformed datasets, invalid files, audit records, and processing artifacts. |
| 4 | AWS Secrets Manager | Security | Centralized credential management for databases, APIs, and other sensitive configuration values. |
| 5 | EC2 `huynm43-mp-ec2-airflow` | Compute & Orchestration | Hosts Apache Airflow and executes pipeline orchestration logic. Responsible for scheduling, dependency management, monitoring task execution, and initiating data processing workflows. |
| 6 | Airflow `PythonOperator` (RCV -> L0) | Compute | Executes Pandas-based validation and transformation logic. Reads files from the `rcv` layer, validates file structure and data quality, moves invalid files to `quarantine`, and writes validated output to `l0`. |
| 7 | Airflow `PythonOperator` (L0 -> L1) | Compute | Executes Pandas-based business transformation and data quality rules. Reads validated data from `l0`, isolates invalid records into `audit`, and writes business-ready datasets into `l1`. |
| 8 | Airflow `PythonOperator` (L1 -> RDS PostgreSQL) | Compute | Executes Pandas-based scripts loading data from `l1` to `RDS PostgreSQL` |
| 9 | Amazon RDS PostgreSQL | Database | Serves as the final curated data store for reporting, analytics, and downstream applications. Supports Full Load, Upsert, and Append-Only ingestion strategies. |
| 10 | S3 Gateway Endpoint | Network | Provides private connectivity between EC2 and Amazon S3 without requiring internet or NAT Gateway access. |
| 11 | VPC (`huynm43-mp-vpc`) | Network | Provides network isolation for platform resources and enforces secure communication paths between components. |
| 12 | CloudWatch | Monitoring | Collects logs, metrics, and operational events from Airflow, EC2, and data processing tasks. Supports troubleshooting and operational monitoring. |
| 13 | SNS `huynm43-mp-sns` | Alerting | Sends notifications when pipeline failures occur. Airflow tasks publish alerts using standardized error messages for easier incident investigation. |
| 14 | DynamoDB `huynm43-mp-dynamo` | Audit & Tracking | Stores job execution metadata, pipeline status, processing history, error tracking information, and supports idempotent reruns. |

## Compute & Orchestration Layer
### AWS EC2 – `huynm43-mp-ec2-airflow` (Public Subnet)
- Hosts **Apache Airflow** and acts as a **orchestration and compute layer**.
- Airflow triggers Pandas scripts via PythonOperator.
- The Airflow worker serves as the main compute resource.
  - Note: The data volume must be small. This architecture is only appropriate for testing.
  - For large-volume data, use Glue instead. (See [Glue architecture](./architecture_glue.md).)
- Airflow monitors job execution status and coordinates pipeline dependencies.
- DAG source code is loaded from the `ec2-airflow/` S3 prefix, which contains `dags/` and `scripts/` (Python code used to process data with Pandas).

## Database Layer (Amazon RDS PostgreSQL)
- Amazon RDS PostgreSQL serves as the final persistent data store.
- Stores curated business-ready datasets generated from the L1 layer.
- Acts as the serving layer for downstream applications, dashboards, reporting systems, and data analysts.
- Supports multiple ingestion patterns including:
  - Full Load (Truncate & Insert)
  - Upsert (Insert/Update)
  - Append-Only


## Security & Credential Management
### AWS Secrets Manager
- AWS Secrets Manager remains the central credential repository.
- Secrets are managed independently from application code and infrastructure configuration.

### PostgreSQL Password Handling Pattern
- EC2 retrieves secrets from AWS Secrets Manager, and the Python scripts retrieve the secrets from EC2.
- This allows the RDS database to be accessed and processed when the PythonOperator is triggered.

## Network Architecture (VPC)
### Design

The solution is deployed within a dedicated VPC:

```text
VPC
├── Public Subnet
│   └── EC2 Airflow
│
├── Private Subnet
│   └── Amazon RDS PostgreSQL
│
└── S3 Gateway Endpoint
```

### Public Subnet
- The Airflow EC2 instance is deployed in a Public Subnet because:
    - Administrators may access the server for maintenance and troubleshooting.
    - Airflow's web interface can be exposed through controlled security group rules.
    - The instance serves as an orchestrator.
    - Airflow accesses S3 for processing through PythonOperator and can access RDS easily.

### Private Subnet
- Amazon RDS PostgreSQL

### Amazon S3 Gateway Endpoint
- EC2 access Amazon S3 through an **S3 Gateway Endpoint**.
- Advantages include:
    - No public internet traversal is required.
    - No NAT Gateway is required for S3 access.
    - Reduced networking cost compared to internet-based traffic.
    - Improved security posture by keeping data transfers private.

- This mechanism is used for:
    - Reading Airflow DAGs/Scripts.
    - Reading YAML configuration files.
    - Reading source datasets.
    - Writing l0/l1/audit/quarantine outputs.

### Security Groups
- Security Groups enforce network-level access controls:

**EC2 Airflow Security Group**
- Inbound:
  - None (Use tailscale as Mesh VPN, allows only machine that is in the same VPN to access, so that can ssh into EC2 and airflowUI via machine that is login into that tailscale's account).
- Outbound:
  - Every https.
  - RDS PostgreSQL Security Group.

**RDS PostgreSQL Security Group**
- Accepts PostgreSQL traffic only from:
  - Airflow EC2 Security Group (if metadata or administrative access is required)

- This ensures PostgreSQL is never publicly reachable.


## Monitoring & Alerting
### Amazon CloudWatch
- Captures logs from:
  - Airflow
  - System events
- Stores operational metrics and execution statistics.

### Amazon SNS – `huynm43-mp-sns`

- Sends notifications when failures occur.
- Airflow raises exceptions using a consistent naming convention:

```text
FAILED_AT_[stage]
```

### DynamoDB – `huynm43-mp-dynamo`

- Tracks pipeline execution states.
- Stores job metadata.
- Supports audit and observability requirements.
- Enables idempotent reruns and execution history analysis.
