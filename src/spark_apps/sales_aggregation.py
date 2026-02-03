"""
Sales Aggregation Spark Application.

Aggregates sales data from the mock warehouse database.
Demonstrates Spark integration with PostgreSQL and data processing.
"""

import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, col, count, sum


def main():
    """Run sales aggregation Spark job."""
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: sales_aggregation.py <warehouse_jdbc_url> [output_path]", file=sys.stderr)
        sys.exit(1)

    warehouse_url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/sales_aggregation_output"

    # Database connection properties
    db_properties = {
        "user": "warehouse_user",
        "password": "warehouse_pass",
        "driver": "org.postgresql.Driver",
    }

    # Create Spark session
    spark = (
        SparkSession.builder.appName("SalesAggregation")
        .config("spark.jars.packages", "org.postgresql:postgresql:42.5.0")
        .getOrCreate()
    )

    try:
        # Read fact sales table
        fact_sales = spark.read.jdbc(url=warehouse_url, table="FactSales", properties=db_properties)

        fact_sales.printSchema()

        # Read dimension tables
        dim_customer = spark.read.jdbc(
            url=warehouse_url, table="DimCustomer", properties=db_properties
        )
        dim_product = spark.read.jdbc(
            url=warehouse_url, table="DimProduct", properties=db_properties
        )
        dim_date = spark.read.jdbc(url=warehouse_url, table="DimDate", properties=db_properties)

        # Join fact with dimensions using explicit column conditions
        # to avoid ambiguous column names in downstream operations
        sales_enriched = (
            fact_sales.join(dim_customer, fact_sales.CustomerKey == dim_customer.CustomerKey)
            .drop(dim_customer.CustomerKey)
            .join(dim_product, fact_sales.ProductKey == dim_product.ProductKey)
            .drop(dim_product.ProductKey)
            .join(dim_date, fact_sales.OrderDateKey == dim_date.DateKey)
        )

        # Aggregate by product category
        category_sales = (
            sales_enriched.groupBy("Category")
            .agg(
                count("SalesKey").alias("num_orders"),
                sum("Quantity").alias("total_quantity"),
                sum("TotalAmount").alias("total_revenue"),
                avg("TotalAmount").alias("avg_order_value"),
            )
            .orderBy(col("total_revenue").desc())
        )

        category_sales.show(truncate=False)

        # Aggregate by customer segment
        segment_sales = (
            sales_enriched.groupBy("CustomerSegment")
            .agg(
                count("SalesKey").alias("num_orders"),
                sum("TotalAmount").alias("total_revenue"),
                avg("TotalAmount").alias("avg_order_value"),
            )
            .orderBy(col("total_revenue").desc())
        )

        segment_sales.show(truncate=False)

        # Monthly sales trend
        monthly_sales = (
            sales_enriched.groupBy("Year", "Month")
            .agg(
                count("SalesKey").alias("num_orders"),
                sum("TotalAmount").alias("total_revenue"),
            )
            .orderBy("Year", "Month", ascending=[False, False])
            .limit(12)
        )

        monthly_sales.show(truncate=False)

        # Top products by revenue
        top_products = (
            sales_enriched.groupBy("ProductKey", "ProductName", "Category")
            .agg(
                sum("TotalAmount").alias("total_revenue"),
                sum("Quantity").alias("total_quantity"),
            )
            .orderBy(col("total_revenue").desc())
            .limit(10)
        )

        top_products.show(truncate=False)

        # Save aggregated results

        category_sales.write.mode("overwrite").parquet(f"{output_path}/category_sales")
        segment_sales.write.mode("overwrite").parquet(f"{output_path}/segment_sales")
        monthly_sales.write.mode("overwrite").parquet(f"{output_path}/monthly_sales")
        top_products.write.mode("overwrite").parquet(f"{output_path}/top_products")

        # Summary statistics

    except Exception:
        import traceback

        traceback.print_exc()
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
