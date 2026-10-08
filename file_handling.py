from pathlib import Path
import pandas as pd
import re
import xml.etree.ElementTree as Etree
from entsoe import EntsoeRawClient

import main

# Namespace used by the XML
ns: dict[str, str] = {'ns': 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3'}
TIMESLICE_RES = pd.Timedelta(minutes=15)

def get_api_key() -> str | None:
    path = Path(main.path_ENSTOE_key)
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
        xml_string = client.query_day_ahead_prices(main.country_code, start=ts_prev, end=ts_cur, sequence=1)
        open(main.path_to_outfile, 'w').write(xml_string)

    # Catch any API errors
    except Exception as e:
        print(f'Error making API request: {e}\n')
        return

def update_outfile(ts: pd.Timestamp) -> None:

    # If no data file found, fetch API request after creating file
    outfile_path_obj = Path(main.path_to_outfile)
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

def extract_prices(price_dict: dict[int, float]) -> None:
    # Validity of XML already checked in update_outfile()
    tree = Etree.parse(main.path_to_outfile)
    root = tree.getroot()

    timeref = pd.Timestamp.now()
    start_time = pd.Timestamp(timeref.floor(freq='D'), tz=main.TIMEZONE)

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

def concat_price_dict(price_dict: dict[pd.Timestamp, float]) -> str:
    out = ""
    for position, price in price_dict.items():
        out += f"{position}, Price: {price}€/KWh\n"
    return out

def save_to_file(string: str) -> None:
    # Save content to file
    with open("extracted_prices.txt", "w") as fr:
        fr.write(string)

def can_combine(ref_interval: pd.Interval, next_interval: pd.Interval) -> bool:
    if ref_interval.overlaps(next_interval):
        return True
    else:
        return False

def combine_timeslots(price_dict: dict[pd.Timestamp, float]) -> list:
    timeslots = []
    timeslices_list = []
    for timestamp in price_dict.keys():
        #interval must be closed="both" for the overlapping check later to work.
        timeslice = pd.Interval(timestamp, timestamp + TIMESLICE_RES, closed="both")
        timeslices_list.append(timeslice)

    # Loop over all but the last timeslice in the list, skipping the last item because it cannot possibly be combined with a nonexistent next one
    index = 0
    offset = 0
    lookahead = 1
    list_range = range(len(timeslices_list))
    while index + offset + lookahead in list_range:
        #initialize the start and end timestamps using the current timeslice
        reference_interval = timeslices_list[index]
        interval_start = reference_interval.left
        interval_end = reference_interval.right

        # Step through list range, checking each next slice for a start time matching the previous slice end. if they match, they can be merged into a single bigger slice.
        while index + offset + lookahead in list_range:

            # pd.Interval.Overlaps() checks if the two candidate intervals share an endpoint. only works if the listed slices have closed="both", to enable overlapping at the extreme value.
            # An alternative is to use the start and end timestamps directly.
            if timeslices_list[index + offset].overlaps(timeslices_list[index + offset + lookahead]):
                interval_end = timeslices_list[index + offset + lookahead].right
                offset += 1
            else:
                break

        # Store the position where the stepping loop reached and reset the stepping offset. avoids retrying and creating duplicate entries.
        index = index + offset + lookahead
        offset = 0

        # Create an interval using the timeslice start and end times.
        interval = pd.Interval(interval_start, interval_end, closed="left")
        timeslots.append(interval)

    return timeslots
