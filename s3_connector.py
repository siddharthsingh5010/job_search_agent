"""Simple helper class for common Amazon S3 operations."""

from pathlib import Path
import boto3


class S3Connector:
    """Connect to one S3 bucket and manage its files."""

    def __init__(
        self,
        bucket_name: str,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ):
        self.bucket_name = bucket_name
        self.s3 = boto3.client(
            "s3",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def connect(self) -> bool:
        """Check that the credentials can access the bucket."""
        self.s3.head_bucket(Bucket=self.bucket_name)
        return True

    def download_file(self, s3_file_name: str, local_path: str) -> None:
        """Download a file from S3 to a local path."""
        self.s3.download_file(self.bucket_name, s3_file_name, local_path)

    def upload_file(self, local_path: str, s3_file_name: str | None = None) -> None:
        """Upload a local file. Its local name is used if no S3 name is given."""
        s3_file_name = s3_file_name or Path(local_path).name
        self.s3.upload_file(local_path, self.bucket_name, s3_file_name)

    def delete_file(self, s3_file_name: str) -> None:
        """Delete a file from S3."""
        self.s3.delete_object(Bucket=self.bucket_name, Key=s3_file_name)

    def rename_file(self, old_name: str, new_name: str) -> None:
        """Rename an S3 file by copying it and deleting the old file."""
        copy_source = {"Bucket": self.bucket_name, "Key": old_name}
        self.s3.copy_object(
            Bucket=self.bucket_name,
            CopySource=copy_source,
            Key=new_name,
        )
        self.delete_file(old_name)
