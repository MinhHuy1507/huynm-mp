# Mock Project 01

## Giới thiệu

- Đây là repository sử dụng cho mục đích thực hiện mock project.
- Repo này bao gồm các source code:
  - Local chạy bằng pandas: [src/local/pandas](./src/local/pandas). Chỉ cần làm theo như hướng dẫn bên dưới là chạy được.
  - Local chạy bằng spark: [src/local/spark](./src/local/spark). Cần phải có spark local mới chạy được.
  - Code deploy lên AWS: [src/aws_deploy](./src/aws_deploy).

## Thành viên thực hiện

| STT | Tên thành viên | Account Github |
| --- | --- | --- |
| 1 | **Ngô Minh Huy** | [MinhHuy1507](https://github.com/MinhHuy1507) |

## Trainer hướng dẫn

| STT | Tên trainer |
| --- | --- |
| 1 | **HanhBT4**|

## Các tài liệu
- [Thông tin về mock project](./docs/mock_project/info.md)
- [Phân tích yêu cầu](./docs/mock_project/requirement_analysis.md)

## Cách chạy
### 0. Chuẩn bị
- git clone về
```bash
git clone https://github.com/MinhHuy1507/mock-project-01
```
- cd vào thư mục project
```bash
cd ./mock-project-01
```


### Cách 1: Chạy không cần docker
- Cách chạy không cần docker, tuy nhiên chỉ xử lý dữ liệu từ rcv -> l0 -> l1, không load vào database.

#### 1. Cài đặt các package cần thiết
```bash
python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt
```
#### 2. Thay config
- Vào trong config/global.yaml, thay đổi config path thành

```yaml
path:
  rcv: ../data/rcv/
  l0: ../data/l0/
  l1: ../data/l1/
  job_tracking: ../data/audit/jobtracking/
  error_records: ../data/audit/error_records/
```

#### 2. Chạy thử
```python
cd ./src/local/pandas/
python mock-data.py
python test.py --table customers
```
- Thay argparse để chạy các bảng khác (customers, products, orders, province)

### Cách 2: Chạy bằng docker
#### 1. docker compose
```bash
docker compose up -d --build
```

#### 2. Chạy Dag
- Truy cập http://localhost:8080, đăng nhập bằng user/pass là airflow/airflow.
- Chạy thử dag ops_check_connectivity để kiểm tra kết nối postgres.
- Chạy DAG mock_project để thực hiện pipeline từ rcv -> l0 -> l1 -> database.