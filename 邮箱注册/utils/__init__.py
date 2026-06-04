from faker import Faker
from faker.providers import BaseProvider
import secrets
import string
import re


PASSWORD_SYMBOLS = "!@#$%^&*_-+="
PASSWORD_LENGTH_RANGE = (18, 24)
USERNAME_RANDOM_ALPHABET = string.ascii_lowercase + string.digits
SECURE_RANDOM = secrets.SystemRandom()


MONTHS_MAPPING = {
    '1': 'January',
    '2': 'February',
    '3': 'March',
    '4': 'April',
    '5': 'May',
    '6': 'June',
    '7': 'July',
    '8': 'August',
    '9': 'September',
    '10': 'October',
    '11': 'November',
    '12': 'December'
}

class CountryProvider(BaseProvider):
    def country(self):
        """
        Generate a random country name.

        Returns:
            str: A random country name.
        """
        countries = [
            "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia",
            "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus",
            "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil",
            "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada",
            "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo, Democratic Republic of the",
            "Congo, Republic of the", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czech Republic",
            "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea",
            "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia",
            "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti",
            "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy",
            "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan", "Laos",
            "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar",
            "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico",
            "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar (Burma)",
            "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea",
            "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea",
            "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis",
            "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe",
            "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
            "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan",
            "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste",
            "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine",
            "United Arab Emirates", "United Kingdom", "United States of America", "Uruguay", "Uzbekistan", "Vanuatu",
            "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
        ]
        return self.random_element(countries)

def get_birthdate(birthdate):
    birthdate_split = birthdate.split('-')

    return birthdate_split[0], birthdate_split[1], birthdate_split[2]

def _secure_randint(minimum, maximum):
    return minimum + secrets.randbelow(maximum - minimum + 1)


def _secure_shuffle(values):
    shuffled = list(values)
    SECURE_RANDOM.shuffle(shuffled)
    return shuffled


def _random_password():
    length = _secure_randint(*PASSWORD_LENGTH_RANGE)
    groups = [
        string.ascii_lowercase,
        string.ascii_uppercase,
        string.digits,
        PASSWORD_SYMBOLS,
    ]
    chars = [secrets.choice(group) for group in groups]
    alphabet = "".join(groups)
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    return "".join(_secure_shuffle(chars))


def _clean_username_part(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _random_username(first_name, last_name, birthdate):
    first = _clean_username_part(first_name)
    last = _clean_username_part(last_name)
    year = _clean_username_part(str(birthdate or "").split("-")[-1])[-2:]
    stems = [
        f"{first[:1]}{last[:10]}",
        f"{first[:8]}{last[:6]}",
        f"{last[:8]}{first[:4]}",
        f"mx{first[:4]}{last[:4]}",
    ]
    stem = secrets.choice([item for item in stems if len(item) >= 3] or ["mxmail"])
    if year:
        stem = f"{stem}{year}"
    suffix = "".join(secrets.choice(USERNAME_RANDOM_ALPHABET) for _ in range(_secure_randint(10, 14)))
    username = f"{stem}{suffix}"
    if len(username) < 8:
        username = f"mx{suffix}{''.join(secrets.choice(USERNAME_RANDOM_ALPHABET) for _ in range(6))}"
    return username[:30]


def  generate_missing_info(username, password, first_name, last_name, country, birthdate):
    """
    Generate missing information for a user.

    This function takes in various user information as parameters and generates missing values 
    for them if they are not provided. It uses the Faker library to generate fake data when needed.

    Args:
        username (str): The username of the user.
        password (str): The password of the user.
        first_name (str): The first name of the user.
        last_name (str): The last name of the user.
        country (str): The country of the user.
        birthdate (str): The birthdate of the user in the format 'MM-DD-YYYY'.

    Returns:
        tuple: A tuple containing the generated or provided values for the username, password, 
               first name, last name, country, and birthdate in the same order.

    """
    fake = Faker()
    fake.seed_instance(secrets.randbits(128))
    fake.add_provider(CountryProvider)

    if not password:
        password = _random_password()

    if not first_name:
        first_name = fake.first_name()

    if not last_name:
        last_name = fake.last_name()

    if not country:
        country = fake.country()

    if not birthdate:
        birthdate = fake.date_of_birth(minimum_age=18, maximum_age=60)
        birthdate = f"{birthdate.month}-{birthdate.day}-{birthdate.year}"

    if not username:
        username = _random_username(first_name, last_name, birthdate)
        
    return username, password, first_name, last_name, country, birthdate 

def get_month_by_number(month_number):
    """
    Get the month name by its number.

    Args:
        month_number (str): The number of the month (1-12).

    Returns:
        str: The name of the month.
    """
    return MONTHS_MAPPING.get(month_number.removeprefix('0'), "Invalid month number")
