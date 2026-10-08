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

# Extract prices into dictionary, save that data to file, filter prices and combine timeslots
def update_data() -> str:
    # Fetch time current day
    date_today = pandas.Timestamp.now(tz=TIMEZONE)
    print("Fetched date today: " + str(date_today.year) + "-" + str(date_today.month) + "-" + str(date_today.day))

    fh.update_outfile(date_today)
    fh.extract_prices(price_dict)
    out: str = fh.concat_price_dict(price_dict)
    fh.save_to_file(out)
    #fh.combine_timeslots(price_dict)
    return out

if __name__ == '__main__':
    # Check API key before touching anything else
    if fh.get_api_key() is None:
        exit(1)

    update_data()

    tg.start_bot()

