from pathlib import Path
import pandas
from entsoe import EntsoeRawClient
import pandas as pd
import re
import xml.etree.ElementTree as Etree

# ENTSOE country code
country_code = 'DE_LU'
# Path to the API key
path_to_key: str = 'ENTSOE_API.txt'
# Path to the output file
path_to_outfile: str = 'outfile.xml'
# Namespace used by the XML
ns: dict[str, str] = {'ns': 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3'}
TIMEZONE: str = 'Europe/Brussels'
# Dictionary for time spots
price_dict: dict[int, float] = {}

def get_api_key() -> str | None:


    path = Path(path_to_key)
    # If key file doesn't exist, instantly abort
    if not path.exists():
        print('./' + path.name + ' not found, aborting....')
        return None

    # Read only the first line of file
    line = open(path).read()

    # Find API key match in first line of file and return
    match = re.match(r'[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{12}', line)
    if match is None:
        print('No API valid key format found in file, aborting....')
        # TODO: This return will cause any call of use_api() to not be handled correctly by the caller
        return None
    return match.group(0)

def use_api(ts_prev: pd.Timestamp):

    ts_cur = ts_prev + pd.Timedelta(days=1)

    # If an invalid timestamp is provided, abort
    if pd.isna(ts_prev) or pd.isna(ts_cur):
        print('Invalid timestamp provided, aborting....')
        return

    # Create API client and write to file
    key_match = get_api_key()
    client = EntsoeRawClient(api_key=key_match)
    try:
        xml_string = client.query_day_ahead_prices(country_code, start=ts_prev, end=ts_cur, sequence=1)
        open(path_to_outfile, 'w').write(xml_string)

    # Catch any API errors
    except Exception as e:
        print(f'Error making API request: {e}\n')
        return

def update_outfile(ts: pd.Timestamp) -> None:

    # If no data file found, fetch API request after creating file
    outfile_path_obj = Path(path_to_outfile)
    if not outfile_path_obj.exists():
        print('No data file found, fetching API request....\n')
        outfile_path_obj.touch()
        use_api(ts)

    # Fetch date of existing data file and check against requested day
    else:
        try:
            xml_tree = Etree.parse(outfile_path_obj)
        except Etree.ParseError:
            print('Invalid XML file, fetching API request....\n')
            use_api(ts)
        root = xml_tree.getroot()

        # Extract date from XML file
        time_interval = root.find('.//ns:period.timeInterval', ns)
        if time_interval is not None:
            xml_starttime = time_interval.find('ns:start', ns)
            if xml_starttime is not None and xml_starttime.text is not None:
                curve_start_timestamp = pd.Timestamp(xml_starttime.text.strip())

            # Create timestamp from XML curve end time string
            xml_endtime = time_interval.find('ns:end', ns)
            if xml_endtime is not None and xml_endtime.text is not None:
                curve_end_timestamp = pd.Timestamp(xml_endtime.text.strip())

            if curve_start_timestamp and curve_end_timestamp:
                curve_period = pd.Interval(curve_start_timestamp, curve_end_timestamp, closed="left")
                print(f"Fetched XML date range: {curve_period}" + "\n")

        if not curve_period:
            print('Date in XML not found, fetching API request....\n')
            use_api(ts)

        # If current time is not in the XML daterange, update file through API request
        else:
            if ts in curve_period:
                print('Existing data in XML is up to date!\n')
            else:
                print('Existing data in XML is outdated, fetching API request....\n')
                use_api(ts)

def extract_prices() -> None:
    # Validity of XML already checked in update_outfile()
    tree = Etree.parse(path_to_outfile)
    root = tree.getroot()

    timeref = pd.Timestamp.now()
    TIMESLICE_RES = pd.Timedelta(minutes=15)
    start_time = pd.Timestamp(timeref.floor(freq='D'), tz=TIMEZONE)

    # Find all Point elements regardless of hierarchy depth
    for point in root.findall('.//ns:Point', ns):
        pos_elem = point.find('ns:position', ns)
        price_elem = point.find('ns:price.amount', ns)

        if pos_elem is not None and price_elem is not None and price_elem.text is not None and pos_elem.text is not None:
            pos = int(pos_elem.text.strip())
            time_offset_from_start = pd.Timedelta((TIMESLICE_RES * pos)-TIMESLICE_RES)
            time_pos = start_time + time_offset_from_start
            # Convert from MWh to kWh using 10⁻³ and round to 4 decimal places
            prz = (float(price_elem.text.strip()) * 10 ** -3).__round__(4)
            price_dict[time_pos] = prz


def printf_and_save() -> None:
    # Write content to terminal
    out = ""
    for position, price in price_dict.items():
        out += f"{position}, Price: {price} €/KWh\n"
    print(out)

    # Save content to file
    with open("extracted_prices.txt", "w") as fr:
        fr.write(out)

def filter_prices() -> None:
    # TODO: 1. Clear any spots greater than 0ct/KWh
    pass

def combine_timeslots() -> None:
    # TODO: 2. Combine adjacent time intervals to greater intervals
    pass

if __name__ == '__main__':
    # Check API key before touching anything else
    if get_api_key() is None:
        exit(1)

    # Fetch time current day
    date_today = pandas.Timestamp.now(tz=TIMEZONE)
    print("Fetched date today: " + str(date_today.year) + "-" + str(date_today.month) + "-" + str(date_today.day))

    update_outfile(date_today)

    # Extract prices into dictionary, save that data to file, filter prices and combine timeslots
    extract_prices()
    printf_and_save()
    filter_prices()
    combine_timeslots()


