"""Mock data generator utility using Faker library.

This module provides functions to generate realistic test data for the mock warehouse.
All data generation uses deterministic seeding for reproducibility in tests.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from faker import Faker


class MockDataGenerator:
    """Generate mock warehouse data with realistic patterns and intentional quality issues."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize data generator with deterministic seed.

        Args:
            seed: Random seed for reproducible data generation (default: 42)
        """
        self.fake = Faker()
        Faker.seed(seed)
        self.seed = seed

    def generate_customers(
        self, count: int = 100, null_email_rate: float = 0.02
    ) -> list[dict[str, Any]]:
        """Generate customer dimension records.

        Args:
            count: Number of customer records to generate
            null_email_rate: Percentage of records with missing emails (quality issue)

        Returns:
            List of customer dictionaries with keys: customer_key, customer_name,
            email, country, segment
        """
        customers = []
        segments = ["Enterprise", "SMB", "Consumer"]
        segment_weights = [0.2, 0.4, 0.4]  # 20% Enterprise, 40% SMB, 40% Consumer

        for i in range(1, count + 1):
            # Intentionally include some null emails for quality testing
            # Use random.random() < rate pattern to avoid division by zero when rate is 0
            import random
            email = None if (null_email_rate > 0 and random.random() < null_email_rate) else self.fake.email()

            customer = {
                "customer_key": f"CUST-{str(i).zfill(5)}",
                "customer_name": self.fake.name(),
                "email": email,
                "country": self.fake.country(),
                "segment": self.fake.random_element(elements=segments, weights=segment_weights),
            }
            customers.append(customer)

        return customers

    def generate_products(self, count: int = 50) -> list[dict[str, Any]]:
        """Generate product dimension records.

        Args:
            count: Number of product records to generate

        Returns:
            List of product dictionaries with keys: product_key, product_name,
            category, subcategory, unit_price
        """
        products = []
        categories = ["Electronics", "Clothing", "Food", "Books", "Home"]
        subcategories = ["Accessories", "Main Items", "Supplies", "Parts", "Bundles"]

        for _i in range(1, count + 1):
            product = {
                "product_key": f"PROD-{self.fake.bothify(text='???###')}",
                "product_name": f"{self.fake.word().title()} {self.fake.word().title()}",
                "category": self.fake.random_element(categories),
                "subcategory": self.fake.random_element(subcategories),
                "unit_price": round(self.fake.random_number(digits=3) / 10.0, 2),
            }
            products.append(product)

        return products

    def generate_date_dimension(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Generate date dimension records for a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range (inclusive)

        Returns:
            List of date dictionaries with keys: date_id, date, year, quarter,
            month, month_name, week, day_of_week, day_name, is_weekend, is_holiday
        """
        dates = []
        current_date = start_date

        # Simple holiday list (US holidays for demo)
        holidays = [
            (1, 1),  # New Year's Day
            (7, 4),  # Independence Day
            (12, 25),  # Christmas
        ]

        while current_date <= end_date:
            date_id = int(current_date.strftime("%Y%m%d"))
            day_of_week = current_date.isoweekday()  # 1=Monday, 7=Sunday

            date_record = {
                "date_id": date_id,
                "date": current_date.date(),
                "year": current_date.year,
                "quarter": (current_date.month - 1) // 3 + 1,
                "month": current_date.month,
                "month_name": current_date.strftime("%B"),
                "week": int(current_date.strftime("%U")),
                "day_of_week": day_of_week,
                "day_name": current_date.strftime("%A"),
                "is_weekend": day_of_week in (6, 7),
                "is_holiday": (current_date.month, current_date.day) in holidays,
            }
            dates.append(date_record)
            current_date += timedelta(days=1)

        return dates

    def generate_sales(
        self,
        count: int = 1000,
        customer_ids: list[int] = None,
        product_ids: list[int] = None,
        date_range: tuple = None,
        null_customer_rate: float = 0.02,
        negative_quantity_rate: float = 0.01,
        calculation_error_rate: float = 0.005,
        duplicate_rate: float = 0.03,
    ) -> list[dict[str, Any]]:
        """Generate sales fact records with intentional quality issues.

        Args:
            count: Number of sales records to generate
            customer_ids: List of valid customer IDs to reference
            product_ids: List of valid product IDs to reference
            date_range: Tuple of (start_date, end_date) for sales dates
            null_customer_rate: Rate of orphaned records (quality issue)
            negative_quantity_rate: Rate of negative quantities (quality issue)
            calculation_error_rate: Rate of total amount calculation errors (quality issue)
            duplicate_rate: Rate of duplicate transaction IDs (quality issue)

        Returns:
            List of sales dictionaries with keys: transaction_id, customer_id,
            product_id, sale_date_id, quantity, unit_price, discount, total_amount
        """
        if customer_ids is None:
            customer_ids = list(range(1, 101))
        if product_ids is None:
            product_ids = list(range(1, 51))
        if date_range is None:
            date_range = (datetime(2024, 1, 1), datetime(2024, 12, 31))

        sales = []
        used_transaction_ids = set()

        import random
        for i in range(1, count + 1):
            # Generate or duplicate transaction ID
            # Use random.random() < rate pattern to avoid division by zero
            if duplicate_rate > 0 and random.random() < duplicate_rate and len(used_transaction_ids) > 0:
                # Create duplicate (quality issue)
                transaction_id = self.fake.random_element(list(used_transaction_ids))
            else:
                transaction_id = f"TXN-{self.fake.bothify(text='########')}"
                used_transaction_ids.add(transaction_id)

            # Intentionally create orphaned records (quality issue)
            customer_id = (
                None
                if (null_customer_rate > 0 and random.random() < null_customer_rate)
                else self.fake.random_element(customer_ids)
            )

            product_id = self.fake.random_element(product_ids)

            # Random date within range
            sale_date = self.fake.date_between(start_date=date_range[0], end_date=date_range[1])
            sale_date_id = int(sale_date.strftime("%Y%m%d"))

            # Quantity (with some negative values - quality issue)
            if negative_quantity_rate > 0 and random.random() < negative_quantity_rate:
                quantity = -1 * self.fake.random_int(min=1, max=5)
            else:
                quantity = self.fake.random_int(min=1, max=10)

            unit_price = Decimal(str(self.fake.random_number(digits=2)))
            discount = Decimal(str(self.fake.random_number(digits=1)))

            # Calculate total amount (with some errors - quality issue)
            if calculation_error_rate > 0 and random.random() < calculation_error_rate:
                # Incorrect calculation (missing discount)
                total_amount = quantity * unit_price
            else:
                # Correct calculation
                total_amount = quantity * unit_price - discount

            sale = {
                "transaction_id": transaction_id,
                "customer_id": customer_id,
                "product_id": product_id,
                "sale_date_id": sale_date_id,
                "quantity": quantity,
                "unit_price": float(unit_price),
                "discount": float(discount),
                "total_amount": float(total_amount),
            }
            sales.append(sale)

        return sales

    def generate_staging_sales(
        self,
        count: int = 100,
        customer_ids: list[int] = None,
        product_ids: list[int] = None,
        source_system: str = "POS_SYSTEM",
    ) -> list[dict[str, Any]]:
        """Generate staging sales records (unprocessed raw data).

        Args:
            count: Number of staging records to generate
            customer_ids: List of valid customer IDs to reference
            product_ids: List of valid product IDs to reference
            source_system: Source system identifier

        Returns:
            List of staging sales dictionaries
        """
        if customer_ids is None:
            customer_ids = list(range(1, 101))
        if product_ids is None:
            product_ids = list(range(1, 51))

        staging_records = []

        for i in range(1, count + 1):
            transaction_id = f"TXN-STAGE-{str(i).zfill(6)}"
            customer_id = self.fake.random_element(customer_ids)
            product_id = self.fake.random_element(product_ids)

            # Recent dates for staging
            sale_date = self.fake.date_between(start_date="-30d", end_date="today")
            sale_date_id = int(sale_date.strftime("%Y%m%d"))

            quantity = self.fake.random_int(min=1, max=5)
            unit_price = Decimal(str(self.fake.random_number(digits=2)))
            discount = Decimal(str(self.fake.random_number(digits=1)))
            total_amount = quantity * unit_price - discount

            record = {
                "transaction_id": transaction_id,
                "customer_id": customer_id,
                "product_id": product_id,
                "sale_date_id": sale_date_id,
                "quantity": quantity,
                "unit_price": float(unit_price),
                "discount": float(discount),
                "total_amount": float(total_amount),
                "source_system": source_system,
                "is_processed": False,
            }
            staging_records.append(record)

        return staging_records

    def reset_seed(self, seed: int | None = None) -> None:
        """Reset the random seed for deterministic generation.

        Args:
            seed: New seed value (uses original seed if None)
        """
        if seed is not None:
            self.seed = seed
        Faker.seed(self.seed)


# Convenience function for quick data generation
def generate_mock_warehouse_data(
    customer_count: int = 1000,
    product_count: int = 500,
    sales_count: int = 100000,
    date_range: tuple = None,
    seed: int = 42,
) -> dict[str, list[dict[str, Any]]]:
    """Generate complete mock warehouse dataset.

    Args:
        customer_count: Number of customers to generate
        product_count: Number of products to generate
        sales_count: Number of sales transactions to generate
        date_range: Tuple of (start_date, end_date) for date dimension
        seed: Random seed for reproducibility

    Returns:
        Dictionary with keys: customers, products, dates, sales, staging_sales
    """
    generator = MockDataGenerator(seed=seed)

    if date_range is None:
        date_range = (datetime(2020, 1, 1), datetime(2024, 12, 31))

    # Generate dimensions
    customers = generator.generate_customers(count=customer_count)
    products = generator.generate_products(count=product_count)
    dates = generator.generate_date_dimension(start_date=date_range[0], end_date=date_range[1])

    # Generate facts (using IDs from dimensions)
    customer_ids = list(range(1, customer_count + 1))
    product_ids = list(range(1, product_count + 1))

    sales = generator.generate_sales(
        count=sales_count,
        customer_ids=customer_ids,
        product_ids=product_ids,
        date_range=date_range,
    )

    staging_sales = generator.generate_staging_sales(
        count=1000, customer_ids=customer_ids, product_ids=product_ids
    )

    return {
        "customers": customers,
        "products": products,
        "dates": dates,
        "sales": sales,
        "staging_sales": staging_sales,
    }
