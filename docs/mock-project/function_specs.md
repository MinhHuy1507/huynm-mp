# Các hàm validate và transform từ rcv/ sang l0/
## 1. validate_file
### Purpose
- Dùng để kiểm tra file đầu vào:
    - Có tồn tại không.
    - Có đúng định dạng.
    - Có đọc được không.
    - File có empty không.
    - File chỉ chứa header.
- Nếu file hợp lệ, dữ liệu được đọc thành công.
- Nếu file không hợp lệ, trả về error message, và ghi file ra quarantine/ trong 1 vài Scenarios.
### Input
- Một đường dẫn file ở rcv theo định dạng `rcv/schema_name/table_name/yyyy/mm/dd/table_name.csv`
### Output
- Success: dữ liệu được đọc.
- Failure: trả về error message, ghi file ra quarantine/ trong 1 số Scenarios theo định dạng `quarantine/schema_name/table_name/yyyy/mm/dd/table_name.csv`.

### Scenarios
| Scenario                        | Expected Result                                            |
| ------------------------------- | ---------------------------------------------------------- |
| File không tồn tại              | Message `File not found - (file_path)`       |
| File size = 0 byte              | Message `File empty - (file_path)` và ghi file ra quarantine/      |
| File corrupt hoặc không thể đọc | Message `File is not readable - (file_path)` và ghi file ra quarantine/ |
| File chỉ có header              | Message `File contains only header without data - (file_path)` và ghi file ra quarantine/          |
| File hợp lệ và có dữ liệu       | Dữ liệu trong file được đọc                    |

## 2. validate_schema
### Purpose
- Dùng để kiểm tra dữ liệu đang xử lý so với schema ta định nghĩa trước có:
    - Thêm 1 cột mới.
    - Mất 1 cột.
    - Vừa thêm vừa mất cột.
    - Sai thứ tự cột.
- Nếu schema hợp lệ, không có hành động gì.
- Nếu schema không hợp lệ, trả về error message và ghi file ra quarantine/.

### Input
- Schema của table được định nghĩa trước.
- Schema của dữ liệu đang xử lý.

### Output
- Success: Dữ liệu đang xử lý không bị lệch schema.
- Failure: trả về error message, và ghi file ra quarantine/ với định dạng `quarantine/schema_name/table_name/yyyy/mm/dd/table_name.csv`

### Scenarios
| Scenario                        | Expected Result                                            |
| ------------------------------- | ---------------------------------------------------------- |
| Thêm 1 cột mới              | Message `Schema mismatch. Expected {expected columns}, got {actual columns}`   |
| Mất 1 cột                      | Message `Schema mismatch. Expected {expected columns}, got {actual columns}`   |
| Vừa thêm vừa mất cột             | Message `Schema mismatch. Expected {expected columns}, got {actual columns}`  |
| Sai thứ tự cột | Message `Schema mismatch. Expected {expected columns}, got {actual columns}`  |


## 3. add_columns
### Purpose
- Bổ sung các cột nhằm phục vụ việc tracking, audit và lineage trong pipeline ETL.
- Các cột được thêm sẽ chứa thông tin về:
    - Ngày giờ xử lý dữ liệu (process_date)
    - Nguồn gốc file đầu vào (source_file)

### Input
- Dữ liệu đang xử lý.
- Các cột cần thêm và schema quy định

### Output
- Nếu Success: dữ liệu được thêm các column đã define.
- Nếu Fail: trả về error message.

### Scenarios
| Scenario                                                              | Expected Result                                |
| --------------------------------------------------------------------- | ---------------------------------------------- |
| Rule contains process_date                                            | Cột process_date được thêm vào tất cả records  |
| Rule contains source_file                                             | Cột source_file được thêm vào tất cả records   |
| Rule contains both columns                                            | process_date và source_file  được thêm vào     |
| Rule contains unsupported column                                      | Message `Unknown column name`                  |
| Input Dữ liệu có N records                                          | Output Dữ liệu vẫn có N records              |
| Không có dữ liệu nào bị thay đổi ngoài các cột metadata được thêm mới | Existing column values được giữ nguyên         |

> Case Success:
- Input:

| id | name |
| -- | ---- |
| 1  | John |
| 2  | Mary |

- Output:

| id | name | process_date        | source_file                                   |
| -- | ---- | ------------------- | --------------------------------------------- |
| 1  | John | 2026-09-09 10:00:00 | rcv/retail/customers/2026/09/09/customers.csv |
| 2  | Mary | 2026-09-09 10:00:00 | rcv/retail/customers/2026/09/09/customers.csv |

> Case fail
- Add 1 column mà chưa có trong config -> Message `Unknown column name`.


# Các hàm validate và transform từ l0/ sang l1/
## 1. validate_not_null
### Purpose
- Kiểm tra một cột có chứa giá trị NULL hay không.
- Hàm tạo ra một validation condition dùng để xác định bản ghi nào thỏa mãn quy tắc NOT NULL.

### Input
- Dữ liệu đang xử lý.
- Cột cần được validate.

### Output
- Hàm trả về một validation condition đại diện cho kết quả đánh giá của từng record.
- Validation condition phải trả về:
    - TRUE  -> Record satisfies rule
    - FALSE -> Record violates rule

### Scenarios
| Scenario                       | Expected Result                                  |
| ------------------------------ | ------------------------------------------------ |
| Record chứa giá trị hợp lệ        | Validation result = TRUE                         |
| Record chứa NULL                  | Validation result = FALSE                        |
| Dữ liệu có nhiều records       | Kết quả được đánh giá cho từng record            |


> Example:

| id   | validation_result |
| ---- | ------------------ |
| 1    | TRUE               |
| NULL | FALSE              |
| 3    | TRUE               |
| 4    | TRUE               |
| NULL | FALSE              |

## 2. validate_unique
### Purpose
- Kiểm tra một/nhiều cột có chứa giá trị duplicate không.
- Hàm chỉ dùng cho những cột không phải primary key.
- Hàm tạo ra một validation condition dùng để xác định bản ghi nào thỏa mãn quy tắc unique.
- Hàm sẽ bỏ qua null

### Input
- Dữ liệu đang xử lý.
- Cột cần được validate.

### Output
- Hàm trả về một validation condition đại diện cho kết quả đánh giá của từng record.
- Validation condition phải trả về:
    - TRUE  -> Record satisfies rule
    - FALSE -> Record violates rule

### Scenarios
| Scenario                       | Expected Result                                  |
| ------------------------------ | ------------------------------------------------ |
| Record chứa giá trị hợp lệ        | Validation result = TRUE                         |
| Record chứa giá trị không hợp lệ                  | Validation result = FALSE                        |
| Dữ liệu có nhiều records       | Kết quả được đánh giá cho từng record            |


> Example:

| id   | name      | validation_result  |
| ---- |-----------| ------------------ |
| 1    | Huy       | TRUE               |
| NULL | NULL      | TRUE               |
| 3    | A         | FALSE              |
| 3    | A         | FALSE              |
| 3    | Huy       | TRUE               |

- Giải thích: các record có cặp (id, name) trùng dũ liệu sẽ được đánh dấu FALSE, riêng NULL sẽ được bỏ qua.

## 3. validate_range
### Purpose
- Kiểm tra một cột có chứa giá trị nằm trong khoảng giá trị được định nghĩa hay không.
- Hàm tạo ra một validation condition dùng để xác định bản ghi nào thỏa mãn quy tắc.
- Hàm sẽ bỏ qua null

### Input
- Dữ liệu đang xử lý.
- Cột cần được validate.
- Giá trị tối thiểu mà record được phép.
- Giá trị tối đa mà record được phép.

### Output
- Hàm trả về một validation condition đại diện cho kết quả đánh giá của từng record.
- Validation condition phải trả về:
    - TRUE  -> Record satisfies rule
    - FALSE -> Record violates rule

### Scenarios
| Scenario                       | Expected Result                                  |
| ------------------------------ | ------------------------------------------------ |
| Record chứa giá trị hợp lệ        | Validation result = TRUE                         |
| Record chứa giá trị không hợp lệ                 | Validation result = FALSE                        |
| Dữ liệu có nhiều records       | Kết quả được đánh giá cho từng record            |


> Example: min = 0, max = 100

| kpi  | validation_result  |
| ---- | ------------------ |
|-1.0  | FALSE              |
| 0    | TRUE               |
| 90.0 | TRUE               |
|101.0 | FALSE              |
|NULL  | TRUE               |

- Giải thích: validate range cho cột `kpi`, quy định trong khoảng giá trị [0, 100], ngoài khoảng là FALSE, trong khoảng hoặc chứa giá trị NULL thì TRUE

## 4. validate_format
### Purpose
- Kiểm tra một cột có chứa giá trị đúng với định dạng được định nghĩa hay không.
- Hàm tạo ra một validation condition dùng để xác định bản ghi nào thỏa mãn quy tắc.
- Hàm sẽ bỏ qua null

### Input
- Dữ liệu đang xử lý.
- Cột cần được validate.
- Format quy định.

### Output
- Hàm trả về một validation condition đại diện cho kết quả đánh giá của từng record.
- Validation condition phải trả về:
    - TRUE  -> Record satisfies rule
    - FALSE -> Record violates rule

### Scenarios
| Scenario                       | Expected Result                                  |
| ------------------------------ | ------------------------------------------------ |
| Record chứa giá trị hợp lệ        | Validation result = TRUE                         |
| Record chứa giá trị không hợp lệ                 | Validation result = FALSE                        |
| Dữ liệu có nhiều records       | Kết quả được đánh giá cho từng record            |


> Example: format = "yyyy-mm-dd"

| birthday   | validation_result  |
| ---------- | ------------------ |
| 2026/09/09 | FALSE              |
| 2026-09-09 | TRUE               |
| NULL       | TRUE               |

- Giải thích: validate format cho cột `birthday`, record có giá trị giống format quy định hoặc NULL thì TRUE, khác format thì FALSE

## 5. validate_datatype
### Purpose
- Kiểm tra một cột có chứa giá trị đúng với kiểu dữ liệu đã được định nghĩa hay không.
- Hàm tạo ra một validation condition dùng để xác định bản ghi nào thỏa mãn quy tắc.
- Hàm sẽ bỏ qua null

### Input
- Dữ liệu đang xử lý.
- Cột cần được validate.
- Kiểu dữ liệu quy định

### Output
- Hàm trả về một validation condition đại diện cho kết quả đánh giá của từng record.
- Validation condition phải trả về:
    - TRUE  -> Record satisfies rule
    - FALSE -> Record violates rule

### Scenarios
| Scenario                       | Expected Result                                  |
| ------------------------------ | ------------------------------------------------ |
| Record chứa giá trị hợp lệ        | Validation result = TRUE                         |
| Record chứa giá trị không hợp lệ                 | Validation result = FALSE                        |
| Dữ liệu có nhiều records       | Kết quả được đánh giá cho từng record            |


> Example: datatype = float

| kpi  | validation_result  |
| ---- | ------------------ |
|-1.0  | TRUE              |
| huy  | FALSE               |
| 90.0 | TRUE               |
|NULL  | TRUE               |

- Giải thích: validate datatype cho cột `kpi`, record có kiểu dữ liệu là float hoặc NULL thì TRUE, còn lại FALSE.

## 6. validate_duplicate
### Purpose
- Kiểm tra dữ liệu xem có bị duplicate hay không.
- Hàm này lọc duplicate dựa trên cột primary key nếu có define, còn không thì lọc dựa trên toàn bộ cột
- Hàm tạo ra một validation condition dùng để xác định bản ghi nào thỏa mãn quy tắc.

### Input 
- Dữ liệu đang xử lý.
- Cột primary key (optional), nếu không có thì xử lý trên toàn bộ cột

### Output
- Hàm trả về một validation condition đại diện cho kết quả đánh giá của từng record.
- Validation condition phải trả về:
    - TRUE  -> Record satisfies rule
    - FALSE -> Record violates rule

### Scenarios
| Scenario                           | Expected Result                                        |
| ---------------------------------- | ------------------------------------------------------ |
| Record không duplicate             | Validation result = `TRUE`                             |
| Record duplicate xuất hiện lần đầu | Validation result = `TRUE`                            |
| Record duplicate xuất hiện ở các lần sau | Validation result = `FALSE`                            |
| Dữ liệu có nhiều records           | Kết quả được đánh giá riêng cho từng record            |
| Có từ 2 records trở lên giống nhau | Tất cả records trong nhóm duplicate đều trả về `FALSE` |



> Example: 

| id | name | age | validation_result |
| -: | ---- | --: | :----------------: |
|  1 | Huy  | 21 |       `TRUE`      |
|  2 | An   |  30 |       `TRUE`       |
|  1 | Huy  | 21 |       `FALSE`      |
|  3 | Minh |  28 |       `TRUE`       |
|  4 | Lan  |  22 |       `TRUE`      |
|  4 | Lan  |  22 |       `FALSE`      |
|  4 | Lan  |  22 |       `FALSE`      |

- Giải thích: 
  - Record (2, An, 30) chỉ xuất hiện một lần nên trả về TRUE.
  - Record (3, Minh, 28) chỉ xuất hiện một lần nên trả về TRUE.
  - Hai records (1, Huy,21) có dữ liệu giống nhau hoàn toàn. Record xuất hiện đầu tiên sẽ trả về TRUE, các lần xuất hiện sau là FALSE.
  - Ba records (4, Lan, 22) có dữ liệu giống nhau hoàn toàn. Record xuất hiện đầu tiên sẽ trả về TRUE, các lần xuất hiện sau là FALSE.

## 6. split_customers_name
### Purpose
- Chuẩn hóa cột họ tên khách hàng (name) thành 2 cột riêng biệt là first_name và last_name:
    - first_name: từ cuối cùng trong tên đầy đủ
    - last_name: phần còn lại trước first_name
- Ví dụ: name = "Ngo Minh Huy" thì first_name = "Huy", last_name = "Ngo Minh"

### Input
- Dữ liệu đang xử lý.
- Cột name

### Output
| Column      | Description                    |
| ----------- | ------------------------------ |
| first_name | Từ cuối cùng trong tên         |
| last_name  | Phần còn lại trước first_name |

### Scenarios

| Scenario                     | Expected Result                                    |
| ---------------------------- | -------------------------------------------------- |
| Giá trị NULL                 | first_name và last_name đều NULL                 |
| Một từ                       | first_name chứa giá trị, last_name = NULL        |
| Hai từ                       | first_name là từ cuối, last_name là từ đầu       |
| Nhiều từ                     | first_name là từ cuối, last_name là phần còn lại |
| Nhiều khoảng trắng liên tiếp | Khoảng trắng được chuẩn hóa trước khi tách         |
| Dữ liệu có N records         | Output vẫn có N records                            |
| Không thay đổi các cột khác  | Chỉ bổ sung hoặc cập nhật các cột đầu ra           |

Example
| name | first_name | last_name|
|-|-|-|
| NULL |NULL|NULL|
| Huy | Huy | NULL |
| Ngo Huy | Huy | Ngo |
|Ngo Minh Huy| Huy | Ngo Minh |
|Ngo Minh (lots of space) Huy| Huy | Ngo Minh |


## 7. split_customers_address
### Purpose
- Chuẩn hóa cột address của table customers thành 2 cột riêng biệt là address và address_province:
    - address: address được chuẩn hóa (xóa space, xóa ký tự thừa ở đầu và cuối chuỗi)
    - address_province: Tách phần province của address đã chuẩn hóa

- Quy định: address sẽ có dạng: <số nhà> <tên đường>, <tỉnh/ tp (province)>
- Ví dụ: 123 Nguyen Ai Quoc, Ho Chi Minh.
    - address sẽ là 123 Nguyen Ai Quoc, Ho Chi Minh.
    - address_province là Ho Chi Minh.

### Input
- Dữ liệu đang xử lý.
- Cột address

### Output

| Column      | Description                    |
| ----------- | ------------------------------ |
| address | Giữ nguyên address đầu vào         |
| address_province  | extract từ address |

### Scenarios

| Scenario                                                                  | Expected Result                                                                       |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Giá trị NULL                                                              | address và address_province đều NULL                                              |
| Địa chỉ không chứa dấu phẩy                                               | address được chuẩn hóa, address_province = NULL                               |
| Địa chỉ chỉ chứa một từ  | address được chuẩn hóa, address_province = NULL                               |
| Địa chỉ chứa province ở cuối | address được chuẩn hóa, address_province = "Ho Chi Minh"                       |
| Địa chỉ chứa nhiều dấu phẩy                                               | address_province` được xác định từ thành phần cuối cùng có giá trị sau khi chuẩn hóa |
| Có dấu phẩy ở đầu hoặc cuối chuỗi                                         | Các dấu phẩy dư được loại bỏ trước khi xử lý                                          |
| Có nhiều khoảng trắng liên tiếp                                           | Khoảng trắng được chuẩn hóa trước khi xử lý                                           |
| Thành phần province sau khi chuẩn hóa là chuỗi rỗng                       | address_province` = NULL                                                             |
| Dữ liệu có N records                                                      | Output vẫn có N records                                                               |
| Không thay đổi các cột khác                                               | Chỉ cập nhật hoặc bổ sung các cột đầu ra được cấu hình                                |


Example
| Input Address                                 | Output Address                                | Output Province |
| --------------------------------------------- | --------------------------------------------- | --------------- |
| NULL                                        | NULL                                       | NULL         |
| Ho Chi Minh                                 | Ho Chi Minh                                 | NULL          |
| 123 Nguyen Ai Quoc                          | 123 Nguyen Ai Quoc                          | NULL          |
| 123 Nguyen Ai Quoc, Ho Chi Minh             | 123 Nguyen Ai Quoc, Ho Chi Minh             | Ho Chi Minh   |
| 123 Nguyen Ai Quoc, District 1, Ho Chi Minh | 123 Nguyen Ai Quoc, District 1, Ho Chi Minh | Ho Chi Minh   |
| ,123 Nguyen Ai Quoc, Ho Chi Minh,           | 123 Nguyen Ai Quoc, Ho Chi Minh             | Ho Chi Minh   |
| 123 Nguyen Ai Quoc, , Ho Chi Minh           | 123 Nguyen Ai Quoc, Ho Chi Minh             | Ho Chi Minh   |


## 8. rename_columns
### Purpose
- Chuẩn hóa tên cột trong dữ liệu theo quy tắc được định nghĩa.

### Input
- Dữ liệu đang xử lý
- Cột cần được rename
- Tên cột mới

### Output
- Cột được rename theo tên đã define

### Scenarios
| Scenario                      | Expected Result                   |
| ----------------------------- | --------------------------------- |
| Dữ liệu chứa cột nguồn        | Cột được đổi tên theo cấu hình    |
| Rename một cột                | Chỉ cột được chỉ định bị thay đổi |
| Rename nhiều cột              | Tất cả mapping được áp dụng       |
| Dữ liệu có N records          | Output vẫn có N records           |
| Giá trị dữ liệu không đổi     | Chỉ thay đổi tên cột              |
| Không thay đổi thứ tự records | Thứ tự records được giữ nguyên    |
| Các cột không được mapping    | Được giữ nguyên                   |
| Các cột cần được rename không tồn tại trong dữ liệu    | Message `Columns not found: (columns input)`                   |

> Example

- Input:

| id | name |
| ------------ | -------------- |
| 1            | Huy            |


- Output

| customer_id | customer_name |
| ------------ | -------------- |
| 1            | Huy            |

## 9. filter_columns
### Purpose
- Lựa chọn các cột cần thiết từ dữ liệu.
    - Loại bỏ cột không sử dụng
    - Chuẩn hóa output schema
    - Giảm lượng dữ liệu cần lưu trữ hoặc xử lý

### Input
- Dữ liệu đang xử lý
- Các cột cần được filter

### Output
- Các cột cần thiết được giữ lại theo như define trong table config

### Scenarios

| Scenario                              | Expected Result                                      |
| ------------------------------------- | ---------------------------------------------------- 
| Các cột được chọn                        | Output chứa đúng các cột được cấu hình             |
| Dữ liệu có cột không nằm trong output | Các cột đó bị loại bỏ                                  |
| Dữ liệu có N records                  | Output vẫn có N records                                 |
| Giá trị dữ liệu không thay đổi        | Dữ liệu trong các cột được giữ lại không bị thay đổi |
| Thứ tự cột trong output được cấu hình | Output column order phải giống cấu hình output         |
| Các cột được filter không có trong dữ liệu | Message `Columns not found: (columns filter)`   |

# Các hàm từ l1/ load database rds postgres
## 1. create_table
### Purpose
- Dùng để tạo table với schema rõ ràng trong database dựa trên table config.
- Mục tiêu là đảm bảo hệ thống có thể tự động khởi tạo các bảng phục vụ lưu trữ dữ liệu.

### Input
- Schema bao gồm (tên cột, kiểu dữ liệu, constraint).

### Output
- Bảng được khởi tạo trong database

### Scenarios
| Scenario                              | Expected Result                                      |
| ------------------------------------- | ---------------------------------------------------- 
| Bảng chưa tồn tại                       | Bảng sẽ được khởi tạo với schema define               |
| Bảng đã tồn tại | Không có hành động xảy ra                               |
| Schema định nghĩa mà database không hỗ trợ | Bắt được message của hệ thống và trả về                             |

## 2. append_only
### Purpose
- Dùng để đưa dữ liệu từ layer l1/ trên s3 vào database theo phương thức append only.
- Append only là thêm dữ liệu vào cuối bảng đã có sẵn mà không ghi đè dữ liệu đã tồn tại.

### Input
- Dữ liệu được đọc từ l1.

### Output
- Dữ liệu được load vào db theo phương thức append only.
- Nếu có lỗi thì sẽ bắt lỗi của hệ thống và trả về.

### Scenarios
| Scenario                              | Expected Result                                      |
| ------------------------------------- | ---------------------------------------------------- 
| Bảng chưa tồn tại                       | Error Message `There is no table (table_name)`              |
| Bảng chưa có dữ liệu | Dữ liệu được thêm vào bảng thành công  |
| Bảng đã có dữ liệu | Dữ liệu được thêm vào bảng, không ghi đè dữ liệu trước đó   |
| Dữ liệu mới trùng key với dữ liệu cũ | Bắt lỗi từ database và trả về. |

## 3. truncate_and_insert
### Purpose
- Dùng để đưa dữ liệu từ layer l1/ trên s3 vào database theo phương thức truncate_and_insert.
- Truncate and insert là 1 phương pháp xóa dữ liệu trong bảng đã có sẵn (vẫn giữ schema, index, constraint...) và insert dữ liệu mới vào.

### Input
- Dữ liệu được đọc từ l1.

### Output
- Dữ liệu được load vào db theo phương thức truncate_and_insert.
- Nếu có lỗi thì sẽ bắt lỗi và trả về.

### Scenarios
| Scenario                              | Expected Result                                      |
| ------------------------------------- | ---------------------------------------------------- 
| Bảng chưa tồn tại                       | Error Message `There is no table (table_name)`              |
| Bảng chưa có dữ liệu | Dữ liệu được thêm vào bảng thành công  |
| Bảng đã có dữ liệu | Dữ liệu cũ sẽ bị xóa và thêm dữ liệu mới vào  |

## 4. upsert
### Purpose
- Dùng để đưa dữ liệu từ layer l1/ trên s3 vào database theo phương thức upsert.
- Upsert là phương thức load dữ liệu trong đó hệ thống sẽ cập nhật các bản ghi đã tồn tại và thêm mới các bản ghi chưa tồn tại dựa trên khóa định danh (Primary Key hoặc Business Key).

### Input
- Dữ liệu được đọc từ l1.

### Output
- Dữ liệu được load vào db theo phương thức upsert.
- Nếu có lỗi thì sẽ bắt lỗi và trả về.

### Scenarios
| Scenario                              | Expected Result                                      |
| ------------------------------------- | ---------------------------------------------------- 
| Bảng chưa tồn tại                       | Error Message `There is no table (table_name)`              |
| Bảng chưa có dữ liệu | Dữ liệu được thêm vào bảng thành công  |
| Bảng đã có dữ liệu | Dữ liệu mới thêm vào so với dữ liệu cũ, nếu giống key thì update, khác thì append vào |
