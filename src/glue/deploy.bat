@echo off
set BUCKET_NAME=huynm43-mock-project-s3-414061810527-us-east-1-an
set S3_PATH_GLUE=s3://%BUCKET_NAME%/glue

set GLUE_S3_PROCESS=%S3_PATH_GLUE%/huynm43-mp-glue.py
set GLUE_RDS_LOAD=%S3_PATH_GLUE%/huynm43-mp-glue-load-db.py
set S3_LIBS=%S3_PATH_GLUE%/libs

set ZIP_FILE=commons.zip
set SOURCE_DIR=commons

if exist "%ZIP_FILE%" del "%ZIP_FILE%"

python -m zipfile -c "%ZIP_FILE%" "%SOURCE_DIR%"

aws s3 cp "%ZIP_FILE%" "%S3_PATH_GLUE%/%ZIP_FILE%"
aws s3 cp huynm43-mp-glue.py "%GLUE_S3_PROCESS%"
aws s3 cp huynm43-mp-glue-load-db.py "%GLUE_RDS_LOAD%"
aws s3 sync glue_libs/ "%S3_LIBS%/"