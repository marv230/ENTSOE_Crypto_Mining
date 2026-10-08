import file_handling as fh
import telegram_bot as tg

# ENTSOE country code
country_code = 'DE_LU'

# Path to the API key of ENTSOE and Telegram token
path_ENSTOE_key: str = './ENTSOE_API'
path_Telegram_token: str = './Telegram_API'

# Path to the output file
path_to_outfile: str = './outfile.xml'

TIMEZONE: str = 'Europe/Brussels'

price_dict: dict[int, float] = {}

import pandas

if __name__ == '__main__':
    # Check API key before touching anything else
    if fh.get_api_key() is None:
        exit(1)

    # Fetch time current day
    date_today = pandas.Timestamp.now(tz=fh.TIMEZONE)
    print("Fetched date today: " + str(date_today.year) + "-" + str(date_today.month) + "-" + str(date_today.day))

    fh.update_outfile(date_today)

    # Extract prices into dictionary, save that data to file, filter prices and combine timeslots
    fh.extract_prices()
    fh.printf_and_save()
    fh.filter_prices()
    fh.combine_timeslots()
    prices = fh.get_price_dict()

