import pandas as pd
import time
import requests
import bs4 as bs
from polygon import RESTClient
from config import API_KEY

def get_sp500_tickers():
    """Scrapes the list of S&P 500 tickers from Wikipedia."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    resp = requests.get('http://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
    soup = bs.BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', {'class': 'wikitable'})
    if table is None:
        print("Error: Could not find the S&P 500 table on the Wikipedia page.")
        return []
    tickers = []
    for row in table.find_all('tr')[1:]:
        ticker = row.find_all('td')[0].text.strip()
        # Some tickers on Wikipedia use a '-' instead of a '.' (e.g., BRK-B).
        # The Polygon API expects a '.' so we need to replace it.
        if "-" in ticker:
            ticker = ticker.replace("-", ".")
        tickers.append(ticker)
    return tickers

def fetch_daily_data(client, ticker):
    """Fetches historical daily price data for a given ticker."""
    aggs = client.get_aggs(ticker, 1, "day", "2023-01-01", "2023-12-31")
    if not aggs:
        return pd.DataFrame()

    df = pd.DataFrame(aggs)
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("date")
    return df

def calculate_bollinger_bands(df, window=20, num_std_dev=2):
    """Calculates Bollinger Bands."""
    df['bb_middle'] = df['close'].rolling(window=window).mean()
    df['bb_std'] = df['close'].rolling(window=window).std()
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * num_std_dev)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * num_std_dev)
    return df

def calculate_rsi(df, window=14):
    """Calculates the Relative Strength Index (RSI)."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def main():
    """Main function to run the stock scanner."""
    tickers = get_sp500_tickers()
    print(f"Scanning {len(tickers)} tickers...")

    client = RESTClient(API_KEY)

    print("Scanning for stocks that are below the lower Bollinger Band and have an RSI < 30...")
    for ticker in tickers:
        daily_data = fetch_daily_data(client, ticker)
        if not daily_data.empty:
            daily_data = calculate_bollinger_bands(daily_data)
            daily_data = calculate_rsi(daily_data)

            latest_data = daily_data.iloc[-1]

            if latest_data['close'] < latest_data['bb_lower'] and latest_data['rsi'] < 30:
                print(f"ALERT for {ticker}:")
                print(f"  - Price: {latest_data['close']} is below Lower Bollinger Band: {latest_data['bb_lower']:.2f}")
                print(f"  - RSI: {latest_data['rsi']:.2f} is below 30")
                print("-" * 30)

        time.sleep(13) # Wait for 13 seconds to avoid rate limiting (5 req/min).

if __name__ == "__main__":
    main()
