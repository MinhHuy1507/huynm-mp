# Table Configuration

The YAML files under `config/` are the contract between the pipeline and the
retail data. They describe the S3 layer, file format, expected columns,
validation rules, transformations, and database loading behavior. They are
used by both the AWS Glue and Pandas implementations.

```text
config/
├── rcv/  # Incoming CSV files
├── l0/   # Validated CSV files with technical metadata
└── l1/   # Curated Parquet files loaded into PostgreSQL
```

Each layer contains one file for each supported table:
`customers`, `orders`, `products`, and `province`.

## S3 Paths

The processing code builds paths using this pattern:

```text
s3://{bucket}/{layer}/{schema}/{table}/{process_date}/{table}.{format}
```

For example, a customer input for `2026/09/18` is stored at:

```text
s3://{bucket}/rcv/retail/customers/2026/09/18/customers.csv
```

The RCV configuration also supplies the `quarantine` prefix. The L0
configuration supplies the `audit` prefix. A file that fails file or schema
validation goes to `quarantine`; records that fail L0 business validation go
to `audit`.

## RCV Configuration

An RCV file defines the incoming schema and file-level checks. Example:
`config/rcv/customers.yaml`.

```yaml
table_name: customers
schema_name: retail
rcv_layer: rcv
l0_layer: l0
quarantine_layer: quarantine
rcv_format: csv
l0_format: csv
quarantine_format: csv

columns:
  - name: id
    type: string
  - name: name
    type: string
  - name: birthday
    type: date
    format: YYYY-MM-DD
  - name: address
    type: string
  - name: kpi
    type: decimal

validation:
  validate_file: true
  validate_schema: true

transformation:
  add_column:
    - name: process_date
      type: datetime
    - name: source_file
      type: string
```

`validate_file` checks that the source can be read and contains data.
`validate_schema` checks the incoming columns against the configured columns.
The `add_column` entries describe technical fields added before writing L0.

## L0 Configuration

An L0 file keeps the source fields, adds technical fields, and declares
record-level business validation and transformations. Example:
`config/l0/customers.yaml`.

```yaml
l0_layer: l0
l1_layer: l1
audit_layer: audit
l0_format: csv
l1_format: parquet
audit_format: parquet

validation:
  - rule: not_null
    column: [id, name, birthday, address, kpi, source_file, process_date]
  - rule: range
    column: kpi
    min: 0
    max: 100
  - rule: duplicate
    primary_key: id

transformation:
  split_name:
    - from: name
      to: [first_name, last_name]
  split_address:
    - from: address
      to: [address, address_province]
  rename:
    - from: id
      to: customer_id
  filter_columns:
    - output: [customer_id, first_name, last_name, birthday, address, address_province, kpi, process_date, source_file]
```

The supported configuration forms used by the repository are:

- `not_null`: all listed columns must have values.
- `range`: a numeric column must be between `min` and `max`.
- `duplicate`: rejects duplicate values for `primary_key`.
- `unique`: rejects duplicate combinations in the listed `column` values.
- `split_name` and `split_address`: create the configured output columns.
- `rename`: renames a column before output.
- `filter_columns`: selects and orders the final L1 columns.

## L1 Configuration

An L1 file defines the curated output schema and the PostgreSQL load strategy.
Example: `config/l1/customers.yaml`.

```yaml
schema_name: retail
table_name: customers
l1_layer: l1
l1_format: parquet

columns:
  - name: customer_id
    type: string
    db_type: VARCHAR
    max_length: 20
    primary_key: true
  - name: kpi
    type: double
    db_type: DOUBLE
    not_null: true
    range: [0, 100]

load_database:
  load_strategy: upsert
  primary_key: customer_id
```

Column metadata includes the logical `type`, PostgreSQL `db_type`, optional
`max_length`, `precision`, `scale`, `primary_key`, `not_null`, and `range`.
The complete column list in each L1 file is the schema written to Parquet and
used to create the PostgreSQL table.

The repository currently configures these load strategies and keys:

| Table | L1 primary key | Load strategy |
|---|---|---|
| `customers` | `customer_id` | `upsert` |
| `orders` | `order_id` | `append_only` |
| `products` | `product_id` | `upsert` |
| `province` | `province_id` | `truncate_and_insert` |


## Configuration Summary

| Layer | Input/output | Main responsibility |
|---|---|---|
| RCV | CSV -> L0 CSV | File and schema validation; add `process_date` and `source_file`. |
| L0 | L0 CSV -> L1 Parquet | Record validation, business transformations, and audit output. |
| L1 | L1 Parquet -> PostgreSQL | Final schema, database types, constraints, and loading strategy. |
