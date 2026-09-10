# **Analyze Mock Project**
## Overview
- type: batch processing
- Schedule: every day

## Data Layer
- Có các file csv
    - customer.csv: thông tin khách hàng (id, name, birthday, address, kpi)
    - province.csv: thông tin về tỉnh thành đó (có thể là code, province name...)
    - product.csv: thông tin về sản phẩm 
    - orders.csv: thông tin về giao dịch.

- Tổ chức lưu trữ:
```
RCV/{schema_name}/{table_name}/yyyy/mm/dd/{table_name}.csv
L0/{schema_name}/{table_name}/yyyy/mm/dd/{table_name}.csv
L1/{schema_name}/{table_name}/yyyy/mm/dd/{table_name}.parquet
```

- schema_name: quyết định chọn `retail`

## Database Load
- Yêu cầu phải sử dụng cả 3 trường phái: upsert, full load, append-only.
- Dự kiến mapping từ dữ liệu raw:
    - upsert: customer, product
    - truncate and insert: province
    - append-only: orders

## Process & Validation
- Từ RVC -> L0:
    - Validation:
        - file có tồn tại ko.
        - file có đúng định dạng csv ko.
        - file có trống ko.
        - file có đọc được ko
        - Xử lý schema drift, nếu schema thay đổi -> quăng vô quarinetine.
    - Transformation
        - Thêm các cột process_date và source_file cho từng table
- L0 -> L1:
    - Validation:
        - validate các cột cần, ví dụ id có null, ...
    - Transformation:
        - Tách các cột cần thiết: name (customer) -> first_name, last_name...
        - Chuyển sang parquet.

- L1 -> RDS Postgres:
    - Áp dụng các kỹ thuật database load nói trên.



## Tables và Schemas
- Cấu trúc lưu trữ
```
RCV
└── retail
    ├── customer
    |   └── yyyy
    |       └── mm
    |           └── dd
    |               └── customer.csv
    ├── province (tương tự trên)
    ├── product (tương tự trên)
    └── orders (tương tự trên)

L0
└── retail
    ├── customer
    |   └── yyyy
    |       └── mm
    |           └── dd
    |               └── customer.csv
    ├── province (tương tự trên)
    ├── product (tương tự trên)
    └── orders (tương tự trên)

L1
└── retail
    ├── customer
    |   └── yyyy
    |       └── mm
    |           └── dd
    |               └── customer.parquet
    ├── province (tương tự trên)
    ├── product (tương tự trên)
    └── orders (tương tự trên)

```

### RCV
- customer
```
id, name, birthday, address, kpi
```
- province
```
id, name
```
- product
```
id, name, unit_price
```
- orders
```
id, customer_id, product_id, quantity, price, orders_date
```

### L0
- customer
```
id, name, birthday, address, kpi, process_date, source_file
```
- province
```
id, name, process_date, source_file
```
- product
```
id, name, unit_price, process_date, source_file
```

- orders
```
id, customer_id, product_id, quantity, price, orders_date, process_date, source_file
```

### L1
- customer
```
customer_id, first_name, last_name, birthday, address, address_province, kpi, process_date
```

- province
```
province_id, province_name, process_date
```

- product
```
product_id, product_name, unit_price, process_date
```

- orders
```
orders_id, customer_id, product_id, quantity, unit_price, total_amount, orders_date, process_date
```

### Audit
- Được ghi vào dynamo
- Sẽ có 2 bảng job_tracking và error_records để track pipeline
- job_tracking: Dùng để track ở từng table ở từng stage trong từng lần chạy pipeline
    - Có trạng thái chính là: STARTED, FAILED, SUCCESS
```
job_id (lấy từ airflow)
execution_id (cũng là airflow, phục vụ track nếu backfill/catchup)
process_date
table_name
stage_name
status
input_count
output_count
error_count
start_time
end_time
error_message
```

- error_records: Dùng để ghi lại những record lỗi, là những records lỗi ở stage (l0 -> l1)
```
job_id
table_name
file_path
error_message
raw_record
process_date
```

## Techstack và môi trường triển khai
- python
- yaml files: cho việc config, xử lý/validate dữ liệu
- AWS:
  - mwaa: airflow managed by aws
  - s3: chứa rcv/, l0/, l1/, dags/, config/
  - lambda: xử lý/validate dữ liệu
  - dynamo: track
  - sns: alert nếu 1 stage trong pipeline failed

## More
- Về idempotency: thiết kế ở từng stage sao cho mỗi lần chạy lại ở cùng 1 thời điểm đều cho kết quả giống nhau.