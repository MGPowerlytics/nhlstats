"""
Centralized naming resolver using canonical_mappings table.
"""
from typing import Optional, Dict
from db_manager import default_db

class NamingResolver:
    _cache: Dict[str, str] = {}

    @classmethod
    def resolve(cls, sport: str, source: str, name: str) -> Optional[str]:
        """
        Resolves an external name to a canonical name.
        Example: resolve('NHL', 'kalshi', 'BOS') -> 'Boston Bruins'
        """
        if not name: return None

        cache_key = f"{sport.upper()}:{source}:{name}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        query = """
            SELECT canonical_name
            FROM canonical_mappings
            WHERE sport = :sport AND source_system = :source AND external_name = :name
        """
        df = default_db.fetch_df(query, {
            'sport': sport.upper(),
            'source': source,
            'name': name
        })

        canonical = df.iloc[0]['canonical_name'] if not df.empty else None
        if canonical:
            cls._cache[cache_key] = canonical
        return canonical

    @classmethod
    def add_mapping(cls, sport: str, source: str, external: str, canonical: str):
        """Manually add a mapping to the database and cache."""
        query = """
            INSERT INTO canonical_mappings (sport, source_system, external_name, canonical_name)
            VALUES (:sport, :source, :external, :canonical)
            ON CONFLICT (sport, source_system, external_name) DO UPDATE SET canonical_name = EXCLUDED.canonical_name
        """
        default_db.execute(query, {
            'sport': sport.upper(),
            'source': source,
            'external': external,
            'canonical': canonical
        })
        cls._cache[f"{sport.upper()}:{source}:{external}"] = canonical
