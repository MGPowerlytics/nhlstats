#!/usr/bin/env python3
"""
Scraper for Hong Kong Jockey Club (HKJC) race results.
Collects race results, horse performances, dividends, and sectional times.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
from pathlib import Path


class HKJCRacingScraper:
    """Scrape race results from Hong Kong Jockey Club website."""
    
    BASE_URL = "https://racing.hkjc.com/racing/information/English/racing"
    RESULTS_URL = f"{BASE_URL}/LocalResults.aspx"
    
    def __init__(self, output_dir="data/hk_racing"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_race_dates(self, start_date=None, end_date=None):
        """
        Get list of race dates.
        Returns dates when races were held at either Happy Valley or Sha Tin.
        """
        if not start_date:
            start_date = datetime.now().date()
        if not end_date:
            end_date = start_date
        
        # For now, return the date range - in production, query the schedule
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        
        return dates
    
    def scrape_race_card(self, race_date, venue="HV"):
        """
        Scrape all races for a specific date and venue.
        
        Args:
            race_date: datetime.date or string in YYYY-MM-DD format
            venue: 'HV' for Happy Valley, 'ST' for Sha Tin
        
        Returns:
            dict with race meeting information and all races
        """
        if isinstance(race_date, str):
            race_date = datetime.strptime(race_date, '%Y-%m-%d').date()
        
        date_str = race_date.strftime('%d/%m/%Y')
        
        params = {
            'RaceDate': date_str,
            'Venue': venue
        }
        
        try:
            response = self.session.get(self.RESULTS_URL, params=params, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            meeting_data = {
                'date': race_date.isoformat(),
                'venue': 'Happy Valley' if venue == 'HV' else 'Sha Tin',
                'venue_code': venue,
                'races': []
            }
            
            # Parse each race on the card
            race_sections = soup.find_all('div', class_='race_section')
            
            for race_section in race_sections:
                race_data = self._parse_race(race_section, race_date, venue)
                if race_data:
                    meeting_data['races'].append(race_data)
            
            return meeting_data
            
        except requests.RequestException as e:
            print(f"Error fetching race data for {date_str}: {e}")
            return None
    
    def _parse_race(self, race_section, race_date, venue):
        """Parse a single race section from the HTML."""
        try:
            # Extract race header info
            race_header = race_section.find('div', class_='race_header')
            if not race_header:
                return None
            
            race_title = race_header.get_text(strip=True)
            
            # Extract race number
            race_num_match = re.search(r'RACE (\d+)', race_title)
            race_number = int(race_num_match.group(1)) if race_num_match else None
            
            # Extract distance
            dist_match = re.search(r'(\d+)M', race_title)
            distance = int(dist_match.group(1)) if dist_match else None
            
            # Extract class
            class_match = re.search(r'Class (\d+)', race_title)
            race_class = int(class_match.group(1)) if class_match else None
            
            # Extract going and course
            going = None
            course = None
            going_elem = race_section.find(text=re.compile('Going'))
            if going_elem:
                going = going_elem.find_next('td').get_text(strip=True)
            
            course_elem = race_section.find(text=re.compile('Course'))
            if course_elem:
                course_text = course_elem.find_next('td').get_text(strip=True)
                course_match = re.search(r'"([A-Z])"', course_text)
                course = course_match.group(1) if course_match else None
            
            # Extract sectional times
            sectional_times = []
            sectional_elem = race_section.find(text=re.compile('Sectional Time'))
            if sectional_elem:
                sectional_text = sectional_elem.find_next('td').get_text(strip=True)
                sectional_times = re.findall(r'(\d+\.\d+)', sectional_text)
            
            race_data = {
                'race_id': f"{race_date.strftime('%Y%m%d')}_{venue}_{race_number:02d}",
                'date': race_date.isoformat(),
                'venue': venue,
                'race_number': race_number,
                'distance': distance,
                'race_class': race_class,
                'going': going,
                'course': course,
                'sectional_times': sectional_times,
                'results': []
            }
            
            # Parse results table
            results_table = race_section.find('table', class_='results')
            if results_table:
                rows = results_table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 10:
                        continue
                    
                    result = {
                        'placing': cols[0].get_text(strip=True),
                        'horse_number': cols[1].get_text(strip=True),
                        'horse_name': cols[2].get_text(strip=True),
                        'jockey': cols[3].get_text(strip=True),
                        'trainer': cols[4].get_text(strip=True),
                        'actual_weight': self._parse_int(cols[5].get_text(strip=True)),
                        'declared_weight': self._parse_int(cols[6].get_text(strip=True)),
                        'draw': self._parse_int(cols[7].get_text(strip=True)),
                        'lengths_behind': cols[8].get_text(strip=True),
                        'finish_time': cols[9].get_text(strip=True) if len(cols) > 9 else None,
                        'win_odds': self._parse_float(cols[10].get_text(strip=True)) if len(cols) > 10 else None
                    }
                    
                    race_data['results'].append(result)
            
            # Parse dividends
            dividends = self._parse_dividends(race_section)
            race_data['dividends'] = dividends
            
            return race_data
            
        except Exception as e:
            print(f"Error parsing race: {e}")
            return None
    
    def _parse_dividends(self, race_section):
        """Parse dividend/payout information."""
        dividends = {}
        
        dividend_section = race_section.find('div', class_='dividend')
        if not dividend_section:
            return dividends
        
        # Common dividend types: WIN, PLACE, QUINELLA, QUINELLA PLACE, TIERCE, TRIO, etc.
        dividend_types = ['WIN', 'PLACE', 'QUINELLA', 'QUINELLA PLACE', 'TIERCE', 'TRIO', 'FIRST 4']
        
        for div_type in dividend_types:
            div_elem = dividend_section.find(text=re.compile(div_type))
            if div_elem:
                value_elem = div_elem.find_next('td')
                if value_elem:
                    dividends[div_type] = value_elem.get_text(strip=True)
        
        return dividends
    
    def _parse_int(self, text):
        """Safely parse integer from text."""
        try:
            return int(re.sub(r'[^\d]', '', text))
        except (ValueError, AttributeError):
            return None
    
    def _parse_float(self, text):
        """Safely parse float from text."""
        try:
            return float(re.sub(r'[^\d.]', '', text))
        except (ValueError, AttributeError):
            return None
    
    def download_race_day(self, race_date, venues=['HV', 'ST']):
        """
        Download all race results for a specific day.
        
        Args:
            race_date: datetime.date or string in YYYY-MM-DD format
            venues: list of venue codes ['HV', 'ST']
        
        Returns:
            dict with all meetings for the day
        """
        if isinstance(race_date, str):
            race_date = datetime.strptime(race_date, '%Y-%m-%d').date()
        
        day_data = {
            'date': race_date.isoformat(),
            'meetings': []
        }
        
        for venue in venues:
            print(f"Scraping {venue} races for {race_date}...")
            meeting = self.scrape_race_card(race_date, venue)
            
            if meeting and meeting.get('races'):
                day_data['meetings'].append(meeting)
                
                # Save individual meeting file
                filename = f"{race_date.strftime('%Y%m%d')}_{venue}.json"
                filepath = self.output_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(meeting, f, indent=2, ensure_ascii=False)
                
                print(f"  Saved {len(meeting['races'])} races to {filepath}")
        
        return day_data
    
    def download_date_range(self, start_date, end_date):
        """Download race results for a date range."""
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        current = start_date
        while current <= end_date:
            try:
                self.download_race_day(current)
            except Exception as e:
                print(f"Error downloading {current}: {e}")
            
            current += timedelta(days=1)


def main():
    """Example usage."""
    scraper = HKJCRacingScraper()
    
    # Example 1: Scrape most recent race day
    yesterday = datetime.now().date() - timedelta(days=1)
    scraper.download_race_day(yesterday)
    
    # Example 2: Scrape specific date
    # scraper.download_race_day('2026-01-14')
    
    # Example 3: Scrape date range
    # scraper.download_date_range('2026-01-01', '2026-01-14')


if __name__ == "__main__":
    main()
