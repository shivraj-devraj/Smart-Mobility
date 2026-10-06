"""Utilities for creating and configuring the project's Spark session."""

import os
import sys

from pyspark.sql import SparkSession


def create_spark_session(app_name: str = "BengaluruTravelSurgeProject") -> SparkSession:
    """Create a local Spark session for development and initial experiments."""
    # Point both Spark's driver and Python workers at the interpreter running this app.
    python_executable = sys.executable
    os.environ["PYSPARK_PYTHON"] = python_executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = python_executable

    # This diagnostic helps verify which interpreter Spark will use on Windows.
    print(f"Python executable: {python_executable}")

    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .getOrCreate()
    )
