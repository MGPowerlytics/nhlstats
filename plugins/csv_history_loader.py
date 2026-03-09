"""
CSV History Loader for sports data.

Responsible for loading historical CSV data for various sports (EPL, Tennis, NCAAB, etc.)
into the PostgreSQL database. Separated from NHLDatabaseLoader to improve
separation of concerns and reduce class size.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict, Callable
from dataclasses import dataclass

from plugins.db_manager import DBManager
from csv_processors import get_csv_processor


@dataclass
class CSVLoadConfig:
    """Configuration for CSV file loading.

    Encapsulates all CSV loading parameters to avoid primitive obsession
    and provide a clean interface for CSV loading configuration.
    """

    # File reading configuration
    encoding: Optional[str] = None
    fallback_encoding: bool = False

    # Date parsing configuration
    date_column: str = "Date"
    date_format: str = "dayfirst"  # "dayfirst" or "monthfirst"
    date_errors: Optional[str] = None  # "coerce", "raise", "ignore"
    require_date_column: bool = True

    # Processing configuration
    metadata_extractor: Optional[Callable[[Path], Dict[str, Any]]] = None
    row_processor: Optional[Callable[[pd.Series, Dict[str, Any]], None]] = None

    # Filtering
    target_date: Optional[str] = None


class CSVHistoryLoader:
    """Loader for historical CSV data across multiple sports."""

    def __init__(self, db_manager: DBManager) -> None:
        """Initialize CSV history loader with database manager.

        Args:
            db_manager: Database manager instance for database operations
        """
        self.db = db_manager

    def _load_history_from_dir(
        self,
        data_dir: Path,
        pattern: str,
        loader_func: Callable,
        sport_name: str,
        target_date: Optional[str] = None,
    ) -> None:
        """Generic CSV history loader to reduce code duplication.

        Args:
            data_dir: Directory containing CSV files
            pattern: Glob pattern for CSV files
            loader_func: Function to call for each CSV file
            sport_name: Name of the sport (for error messages)
            target_date: Optional date filter in YYYY-MM-DD format
        """
        if not data_dir.exists():
            return

        csv_files = list(data_dir.glob(pattern))
        for csv_file in csv_files:
            try:
                loader_func(csv_file, target_date)
            except Exception as e:
                print(f"  Error loading {sport_name} file {csv_file.name}: {e}")

    def _get_csv_history_config(self, sport: str) -> Dict[str, Any]:
        """Get configuration for CSV history loading for a specific sport.

        Args:
            sport: Sport name ("EPL" or "Tennis")

        Returns:
            Dictionary with keys: data_dir, pattern, loader_func, sport_name
        """
        configs = {
            "EPL": {
                "data_dir": Path("data/epl"),
                "pattern": "E0_*.csv",
                "loader_func": lambda file_path, target_date: self._load_csv_for_sport(
                    "epl", file_path, target_date
                ),
                "sport_name": "EPL",
            },
            "Tennis": {
                "data_dir": Path("data/tennis"),
                "pattern": "*_*.csv",
                "loader_func": lambda file_path, target_date: self._load_csv_for_sport(
                    "tennis", file_path, target_date
                ),
                "sport_name": "Tennis",
            },
        }
        return configs.get(sport, {})

    def load_csv_history(
        self,
        sport: str,
        data_dir: Optional[Path] = None,
        target_date: Optional[str] = None,
    ) -> None:
        """Load all available CSV data for a specific sport into PostgreSQL.

        Args:
            sport: Sport name ("EPL" or "Tennis")
            data_dir: Optional directory containing CSV files. If None, uses default from config.
            target_date: Optional date filter in YYYY-MM-DD format.
        """
        config = self._get_csv_history_config(sport)
        if not config:
            raise ValueError(f"No CSV history configuration found for sport: {sport}")

        # Use provided data_dir or default from config
        actual_data_dir = data_dir if data_dir is not None else config["data_dir"]

        self._load_history_from_dir(
            actual_data_dir,
            config["pattern"],
            config["loader_func"],
            config["sport_name"],
            target_date,
        )

    def _process_csv_row(self, sport: str, row: pd.Series, **kwargs) -> None:
        """Process a single CSV game row and upsert into database.

        Args:
            sport: Sport name (e.g., 'ncaab', 'tennis', 'epl')
            row: Pandas Series containing game data
            **kwargs: Additional parameters to pass to the processor
        """
        processor = get_csv_processor(sport, self.db)
        if processor:
            processor.process_row(row, **kwargs)

    def _load_csv_file(
        self,
        file_path: Path,
        config: CSVLoadConfig,
    ) -> None:
        """Generic CSV file loader to reduce code duplication.

        Args:
            file_path: Path to the CSV file
            config: CSV loading configuration
        """
        # Extract metadata from file path if extractor provided
        metadata = self._extract_metadata(file_path, config.metadata_extractor)

        # Read CSV file with optional encoding
        df = self._read_csv_with_encoding(
            file_path, config.encoding, config.fallback_encoding
        )
        if df is None:
            return

        # Validate and parse date column
        df = self._process_date_column(df, config)
        if df is None:
            return

        # Apply date filter if provided
        df = self._apply_date_filter(df, config.target_date, config.date_column)
        if df is None:
            return

        # Process each row
        self._process_rows(df, metadata, config.row_processor)

    def _extract_metadata(
        self,
        file_path: Path,
        metadata_extractor: Optional[Callable[[Path], Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Extract metadata from file path using provided extractor."""
        metadata = {}
        if metadata_extractor:
            metadata = metadata_extractor(file_path)
        return metadata

    def _read_csv_with_encoding(
        self, file_path: Path, encoding: Optional[str], fallback_encoding: bool
    ) -> Optional[pd.DataFrame]:
        """Read CSV file with optional encoding and fallback."""
        # Try with specified encoding first
        df = self._try_read_csv_with_encoding(file_path, encoding)
        if df is not None:
            return df

        # If that fails and fallback is enabled, try without encoding
        if fallback_encoding:
            return self._try_read_csv_without_encoding(file_path)

        # No fallback, return None
        print(
            f"  Error reading CSV file {file_path.name}: Failed with encoding '{encoding}'"
        )
        return None

    def _try_read_csv_with_encoding(
        self, file_path: Path, encoding: Optional[str]
    ) -> Optional[pd.DataFrame]:
        """Try to read CSV file with specified encoding."""
        try:
            read_kwargs = {}
            if encoding:
                read_kwargs["encoding"] = encoding
            return pd.read_csv(file_path, **read_kwargs)
        except Exception:
            return None

    def _try_read_csv_without_encoding(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Try to read CSV file without specifying encoding."""
        try:
            return pd.read_csv(file_path)
        except Exception as e:
            print(f"  Error reading CSV file {file_path.name}: {e}")
            return None

    def _process_date_column(
        self, df: pd.DataFrame, config: CSVLoadConfig
    ) -> Optional[pd.DataFrame]:
        """Validate and parse date column in DataFrame."""
        # Check for required date column
        if config.require_date_column and config.date_column not in df.columns:
            return None

        # Parse date column if it exists
        if config.date_column in df.columns:
            parse_kwargs: Dict[str, Any] = {
                "dayfirst": config.date_format == "dayfirst"
            }
            if config.date_errors:
                parse_kwargs["errors"] = config.date_errors
            df[config.date_column] = pd.to_datetime(
                df[config.date_column], **parse_kwargs
            )

        return df

    def _apply_date_filter(
        self, df: pd.DataFrame, target_date: Optional[str], date_column: str
    ) -> Optional[pd.DataFrame]:
        """Apply date filter to DataFrame if target date provided."""
        if not target_date or date_column not in df.columns:
            return df

        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        filtered_df = df[df[date_column] == target_dt]

        if filtered_df.empty:
            return None

        return filtered_df

    def _process_rows(
        self,
        df: pd.DataFrame,
        metadata: Dict[str, Any],
        row_processor: Optional[Callable[[pd.Series, Dict[str, Any]], None]],
    ) -> None:
        """Process each row in DataFrame using provided processor."""
        if row_processor:
            for _, row in df.iterrows():
                row_processor(row, metadata)

    def _process_ncaab_row(self, row: pd.Series) -> None:
        """Process a single NCAAB game row and upsert into database."""
        self._process_csv_row("ncaab", row)

    def _load_sport_csv(
        self,
        file_path: Path,
        sport: str,
        config: CSVLoadConfig,
    ) -> None:
        """Generic method to load sport CSV files into PostgreSQL.

        Args:
            file_path: Path to the CSV file
            sport: Sport name (e.g., 'tennis', 'epl')
            config: CSV loading configuration
        """
        # Ensure row_processor is set (it should be created by caller with sport parameter)
        if config.row_processor is None:
            raise ValueError("CSVLoadConfig must have a row_processor")
        self._load_csv_file(file_path, config)

    def _get_csv_load_config_for_sport(
        self, sport: str, file_path: Path, target_date: Optional[str] = None
    ) -> CSVLoadConfig:
        """Get CSV load configuration for a specific sport.

        Args:
            sport: Sport name ('tennis' or 'epl')
            file_path: Path to the CSV file
            target_date: Optional date filter in YYYY-MM-DD format

        Returns:
            CSVLoadConfig configured for the specific sport
        """
        if sport == "tennis":
            parts = file_path.stem.split("_")
            if len(parts) < 2:
                raise ValueError(f"Invalid tennis CSV filename: {file_path.name}")
            tour = parts[0].upper()
            season = parts[1]

            return CSVLoadConfig(
                encoding="latin1",
                fallback_encoding=True,
                date_column="Date",
                date_format="dayfirst",
                date_errors="coerce",
                metadata_extractor=lambda fp: {"tour": tour, "season": season},
                row_processor=lambda row, metadata: self._process_csv_row(
                    "tennis", row, tour=metadata["tour"], season=metadata["season"]
                ),
                require_date_column=True,
                target_date=target_date,
            )
        elif sport == "epl":
            season_code = file_path.stem.replace("E0_", "")

            return CSVLoadConfig(
                encoding=None,  # No specific encoding
                fallback_encoding=False,
                date_column="Date",
                date_format="dayfirst",
                date_errors=None,  # No error coercion
                metadata_extractor=lambda fp: {"season_code": season_code},
                row_processor=lambda row, metadata: self._process_csv_row(
                    "epl", row, season_code=metadata["season_code"]
                ),
                require_date_column=False,
                target_date=target_date,
            )
        else:
            raise ValueError(f"Unsupported sport for CSV loading: {sport}")

    def _load_csv_for_sport(
        self,
        sport: str,
        file_path: Path,
        target_date: Optional[str] = None,
    ) -> None:
        """Load CSV file for a specific sport into PostgreSQL.

        Args:
            sport: Sport name ('tennis' or 'epl')
            file_path: Path to the CSV file
            target_date: Optional date filter in YYYY-MM-DD format
        """
        config = self._get_csv_load_config_for_sport(sport, file_path, target_date)
        self._load_sport_csv(file_path=file_path, sport=sport, config=config)
