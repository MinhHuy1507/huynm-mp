# Architecture

## Overview

![Architecture](../assets/architecture_glue.png)


## Component Responsibility

| # | Component | Type | Primary Responsibility |
|---|---|---|---|
| 1 | S3 `ec2-airflow/` and `glue/` | Storage | Stores Apache Airflow DAG source code, and glue source code. |
| 2 | S3 `config/` | Storage | Stores YAML configuration files for each layer (`rcv`, `l0`, `l1`) and table-specific processing rules. |
| 3 | S3 Data Lake (`rcv`, `l0`, `l1`, `quarantine`, `audit`) | Storage | Stores raw files, validated datasets, transformed datasets, invalid files, audit records, and processing artifacts. |
| 4 | EC2 `huynm43-mp-ec2-airflow` | Orchestration | Runs Airflow and triggers Glue Jobs according to scheduling and dependencies |
| 5 | Glue Job `huynm43-mp-glue-processing-layers` | Compute | Processes RCV→L0 and L0→L1 using PySpark |
| 6 | Glue Job `huynm43-mp-glue-load-db` | Compute | Loads L1 datasets into PostgreSQL |
| 7 | Amazon RDS PostgreSQL | Database | Final serving layer for analytics and downstream consumption |
| 8 | S3 Gateway Endpoint | Network | Provides private S3 connectivity for EC2 and Glue Jobs |
| 9 | VPC (`huynm43-mp-vpc`) | Network | Provides network isolation for platform resources and enforces secure communication paths between components. |
| 10 | CloudWatch | Monitoring | Collects logs, metrics, and operational events from Airflow, EC2, and data processing tasks. Supports troubleshooting and operational monitoring. |
| 11 | SNS `huynm43-mp-sns` | Alerting | Sends notifications when pipeline failures occur. Airflow tasks publish alerts using standardized error messages for easier incident investigation. |
| 12 | DynamoDB `huynm43-mp-dynamo` | Audit & Tracking | Stores job execution metadata, pipeline status, processing history, error tracking information, and supports idempotent reruns. |
| 13 | AWS Secrets Manager | Security | Provides centralized credential management for databases, APIs, and other sensitive configuration values. |

## Storage Layer (Amazon S3)
- The solution uses a single Amazon S3 bucket: `huynm43-mock-project-s3-414061810527-us-east-1-an`.
- Data is organized into the following prefixes:
  - `rcv/` – Raw incoming files.
  - `l0/` – Cleansed and validated data.
  - `l1/` – Business-ready transformed data.
  - `quarantine/` – Invalid files isolated for investigation (rcv - l0).
  - `audit/` – Invalid records (l0 - l1).

- Configuration for each table and layer is stored as **YAML files** under:

```text
config/{layer}/{table}.yaml

Examples:
config/rcv/customers.yaml
config/l0/customers.yaml
config/l1/customers.yaml
```

- Two additional code-related prefixes are maintained:
  - `ec2-airflow/` – Stores Apache Airflow DAGs.
  - `glue/` – Stores AWS Glue Job scripts.


## Compute & Orchestration Layer
### AWS EC2 – `huynm43-mp-ec2-airflow` (Public Subnet)
- Hosts **Apache Airflow** and acts as an **orchestration layer**.
- Airflow triggers AWS Glue Jobs through the AWS Glue API (`StartJobRun`) using `GlueJobOperator`.
- Airflow monitors job execution status and coordinates pipeline dependencies.
- DAG source code is loaded from the `ec2-airflow/` S3 prefix.
- Runtime parameters such as bucket, schema, table, layer, and process date are passed to Glue Jobs when they are triggered.

### AWS Glue Job – `huynm43-mp-glue`
- Executes script `huynm43-mp-glue.py`.
- Runs as a managed Apache Spark application on AWS Glue.
- Handles both processing stages:
  - `rcv → l0`
  - `l0 → l1`
- Receives parameters through Glue Job Arguments:
  - `JOB_NAME`
  - `layer`
  - `bucket`
  - `schema`
  - `table`
  - `process_date`
- Loads source code from the `glue/` S3 prefix.
- Uses a dispatcher pattern to route processing logic:

```python
process_layers = {
    "rcv_to_l0": rcv_to_l0,
    "l0_to_l1": l0_to_l1
}
```

- Performs validation, transformation, data quality checks, and file movement between layers.


### AWS Glue Job – `huynm43-mp-glue-load-db`
- Executes script `huynm43-mp-glue-load-db.py`.
- Dedicated to loading data from **L1 into PostgreSQL**.
- Configured to run inside a VPC so it can communicate with Amazon RDS located in a private subnet.
- Receives database connectivity parameters:
  - `pg_username`
  - `pg_password_s3_key`
  - `pg_host`
  - `pg_port`
  - `pg_database`
- Uses Spark and JDBC for bulk loading and may use `psycopg2` for metadata operations or post-load activities.


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

A notable security design decision is that Glue Job `huynm43-mp-glue-load-db` does **not** receive the PostgreSQL password directly through Glue Job parameters.

Instead:

1. The job receives only `pg_password_s3_key`.
2. `pg_password_s3_key` acts as a pointer to a secure object stored in Amazon S3.
3. During runtime, the Glue Job retrieves the file and reads the password:

```python
utils.get_object(...)["Body"].read().decode("utf-8").strip()
```

Benefits:

- Prevents database passwords from appearing in Glue Job arguments.
- Reduces exposure in AWS Glue logs and execution history.
- Keeps sensitive credentials out of orchestration layers.
- Supports centralized secret rotation strategies.


## Network Architecture (VPC)

The platform follows a segregated network architecture designed around security, private connectivity, and least-privilege access.

### VPC Design

The solution is deployed within a dedicated VPC:

```text
VPC
├── Public Subnet
│   └── EC2 Airflow
│
├── Private Subnet
│   ├── AWS Glue ENIs
│   └── Amazon RDS PostgreSQL
│
└── S3 Gateway Endpoint
```

### Public Subnet
- The Airflow EC2 instance is deployed in a Public Subnet because:
    - Administrators may access the server for maintenance and troubleshooting.
    - Airflow's web interface can be exposed through controlled security group rules.
    - The instance serves only as an orchestrator and does not store production data.
    - It can easily retrieve secrets from AWS Secrets Manager without going through any gateway or interface.

### Private Subnet
- Amazon RDS PostgreSQL
- AWS Glue Job network interfaces (ENIs)
- These components avoid direct public internet access.
- Benefits:
    - Reduced attack surface.
    - Stronger isolation of production data.
    - Easier compliance with security best practices.

### AWS Glue Network Connectivity
- When configured with a VPC connection, AWS Glue creates temporary Elastic Network Interfaces (ENIs) inside the target subnet during job execution. Allows:
    - Read and write Amazon RDS PostgreSQL privately.
    - Access VPC resources without traversing the public internet.
    - Operate under VPC security groups and routing rules.

- As a result, the `huynm43-mp-glue-load-db` job can communicate directly with PostgreSQL while remaining fully managed by AWS Glue.

### Amazon S3 Gateway Endpoint
- Both EC2 and Glue Jobs access Amazon S3 through an **S3 Gateway Endpoint**.
- Advantages include:
    - No public internet traversal is required.
    - No NAT Gateway is required for S3 access.
    - Reduced networking cost compared to internet-based traffic.
    - Improved security posture by keeping data transfers private.

- This mechanism is used for:
    - Reading Airflow DAGs.
    - Reading Glue scripts.
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
  - Glue Job Security Group
  - Airflow EC2 Security Group (if metadata or administrative access is required)

- This ensures PostgreSQL is never publicly reachable.


## Monitoring & Alerting
### Amazon CloudWatch

- Centralized logging platform.
- Captures logs from:
  - Airflow
  - AWS Glue Jobs
  - System events
- Stores operational metrics and execution statistics.

### Amazon SNS – `huynm43-mp-sns`

- Sends notifications when failures occur.
- Both Airflow and Glue scripts raise exceptions using a consistent naming convention:

```text
FAILED_AT_[stage]
```

This makes failure localization easier during incident investigation.

### DynamoDB – `huynm43-mp-dynamo`

- Tracks pipeline execution states.
- Stores job metadata.
- Supports audit and observability requirements.
- Enables idempotent reruns and execution history analysis.

