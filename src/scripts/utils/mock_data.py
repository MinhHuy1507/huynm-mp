import argparse
import csv
from io import StringIO
import random
from faker import Faker
from datetime import datetime, timedelta
import time

from scripts.utils.s3_helper import s3


def upload_csv(bucket, key, headers, rows):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=output.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )


def generate_mock_data(bucket, schema, process_date, record_count=100_000):
    start = time.perf_counter()
    fake = Faker("vi_VN")

    def s3_key(table):
        return f"rcv/{schema}/{table}/{process_date}/{table}.csv"

    orders_count = record_count
    customer_count = max(1000, int(orders_count**0.55))
    product_count = int(customer_count * 1.5)

    # Provinces in Vietnam
    PROVINCES = [
        "Ha Noi",
        "Hai Phong",
        "Quang Ninh",
        "Lang Son",
        "Cao Bang",
        "Tuyen Quang",
        "Lao Cai",
        "Thai Nguyen",
        "Phu Tho",
        "Bac Ninh",
        "Hung Yen",
        "Ninh Binh",
        "Thanh Hoa",
        "Nghe An",
        "Ha Tinh",
        "Quang Tri",
        "Hue",
        "Da Nang",
        "Quang Ngai",
        "Gia Lai",
        "Dak Lak",
        "Khanh Hoa",
        "Lam Dong",
        "Dong Nai",
        "Tay Ninh",
        "Ho Chi Minh",
        "Dong Thap",
        "An Giang",
        "Vinh Long",
        "Can Tho",
        "Ca Mau",
        "Kien Giang",
        "Son La",
        "Dien Bien",
    ]

    print("Creating Province data")
    province_rows = [[f"PROV_{i}", name] for i, name in enumerate(PROVINCES, 1)]
    upload_csv(bucket, s3_key("province"), ["id", "name"], province_rows)

    print(f"Province: {time.perf_counter() - start:.3f}s")

    # Products
    start = time.perf_counter()
    print("Creating Products data...")
    POOL_SIZE = 1000
    product_name_pool = [fake.catch_phrase() for _ in range(POOL_SIZE)]
    product_prices = {}
    product_ids = []

    product_rows = []
    for i in range(1, product_count + 1):
        product_id = f"PROD_{i}"
        price = round(random.uniform(10.0, 5000.0), 2)

        product_ids.append(product_id)
        product_prices[product_id] = price
        product_rows.append(
            [product_id, f"{random.choice(product_name_pool)}_{i}", price]
        )
    upload_csv(bucket, s3_key("products"), ["id", "name", "unit_price"], product_rows)

    print(f"Products: {time.perf_counter() - start:.3f}s")

    # Customers
    start = time.perf_counter()
    print(f"Creating data for {customer_count} Customers...")
    NAME_POOL_SIZE = 2000
    STREET_POOL_SIZE = 2000

    last_name_pool = [fake.last_name() for _ in range(300)]
    middle_name_pool = [fake.middle_name() for _ in range(1000)]
    first_name_pool = [fake.first_name() for _ in range(NAME_POOL_SIZE)]
    street_pool = [fake.street_name() for _ in range(STREET_POOL_SIZE)]
    customer_ids = []

    start_birth = datetime(1945, 1, 1)
    end_birth = datetime(2008, 12, 31)
    birth_range_days = (end_birth - start_birth).days

    customer_rows = []
    for i in range(1, customer_count + 1):
        is_error = random.random() < 0.1
        cust_id = f"CUST_{i}"
        customer_ids.append(cust_id)

        name = (
            ""
            if is_error
            else (
                f"{random.choice(last_name_pool)} {random.choice(middle_name_pool)} "
                f"{random.choice(first_name_pool)}"
            )
        )
        birthday_dt = start_birth + timedelta(days=random.randint(0, birth_range_days))
        birthday = birthday_dt.strftime(
            "%d-%m-%Y" if is_error and random.choice([True, False]) else "%Y-%m-%d"
        )
        address = f"{random.choice(street_pool)}, {random.choice(PROVINCES)}"
        kpi = (
            round(random.uniform(101, 200), 2)
            if is_error
            else round(random.uniform(0, 100), 2)
        )
        customer_rows.append([cust_id, name, birthday, address, kpi])
    upload_csv(
        bucket,
        s3_key("customers"),
        ["id", "name", "birthday", "address", "kpi"],
        customer_rows,
    )

    print(f"Customers: {time.perf_counter() - start:.3f}s")

    # Orders
    start = time.perf_counter()
    print(f"Creating {orders_count:,} Orders...")
    base_ts = int(datetime.now().timestamp())

    date_pool = [
        datetime.fromtimestamp(base_ts - random.randint(0, 100)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        for _ in range(1_000)
    ]

    order_rows = []
    for i in range(1, orders_count + 1):
        is_error = random.random() < 0.1
        customer_id = (
            ""
            if is_error and random.choice([True, False])
            else random.choice(customer_ids)
        )
        product_id = random.choice(product_ids)
        quantity = random.randint(-5, 0) if is_error else random.randint(1, 10)
        order_rows.append(
            [
                f"ORD_{i}",
                customer_id,
                product_id,
                quantity,
                product_prices[product_id],
                random.choice(date_pool),
            ]
        )
        if i % 100_000 == 0:
            print(f"  -> Created {i:,} Order rows.")
    upload_csv(
        bucket,
        s3_key("orders"),
        ["id", "customer_id", "product_id", "quantity", "price", "order_date"],
        order_rows,
    )
    print(f"Orders: {time.perf_counter() - start:.3f}s")

    print(f"\n=> COMPLETED! Created data for {record_count:,} records!")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate mock retail data in S3")
    parser.add_argument(
        "--bucket",
        default="huynm43-mock-project-s3-414061810527-us-east-1-an",
        help="S3 bucket name",
    )
    parser.add_argument("--schema", default="retail", help="Schema name")
    parser.add_argument(
        "--process-date",
        default=datetime.now().strftime("%Y/%m/%d"),
        help="Date partition in YYYY/MM/DD format",
    )
    parser.add_argument(
        "--record-count",
        type=int,
        default=100_000,
        help="Number of order records to generate",
    )
    return parser.parse_args()


# Test
if __name__ == "__main__":
    args = parse_args()
    generate_mock_data(
        bucket=args.bucket,
        schema=args.schema,
        process_date=args.process_date,
        record_count=args.record_count,
    )
