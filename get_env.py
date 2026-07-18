from s3_connector import S3Connector

if __name__=="__main__":
    s3 = S3Connector("siddharthsingh701","eu-west-1")
    s3.connect()
    s3.download_file("env_v1", ".env")