"""Small executable check that verifies the initial Spark setup."""

import sys

from src.spark_session import create_spark_session


def main() -> None:
    # Start Spark using the shared project utility.
    spark = create_spark_session("SparkSetupSmokeTest")

    try:
        # Confirm the interpreter used to launch this smoke test.
        print(f"Application Python executable: {sys.executable}")

        # Print the version so the local Spark installation can be verified.
        print(f"Spark version: {spark.version}")

        # Create a small in-memory DataFrame to verify basic Spark SQL support.
        sample_data = [(1, "Weekend"), (2, "Festival")]
        sample_dataframe = spark.createDataFrame(
            sample_data,
            ["event_id", "event_type"],
        )

        # Display the DataFrame in the console.
        sample_dataframe.show()
    finally:
        # Always release the local Spark process after the check completes.
        spark.stop()


if __name__ == "__main__":
    main()
