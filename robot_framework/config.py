"""This module contains configuration constants used across the framework"""
from itk_dev_shared_components.kmd_nova.nova_objects import Caseworker, Department

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.aarhuskommune.local"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"
EFLYT_LOGIN = "Eflyt"
KEYVAULT_CREDENTIALS = "Keyvault"
KEYVAULT_URI = "Keyvault URI"
NOVA_API = "Nova API"

KEYVAULT_PATH = "Godkendelsesbreve_i_eFlyt"

QUEUE_NAME = "Udsendelse af orienteringsbrev om godkendelse af flyttesager"

NOTE_TEXT = "Orientering om godkendelse sendt til anmelder"

# Nova config
CASEWORKER = Caseworker(
        name='Rpabruger Rpa78 - MÅ IKKE SLETTES RITM0283472',
        ident='azrpa78',
        uuid='203e17a1-0032-4f1d-be98-9386e4f2f336'
)

CASE_HEADLINE = "Udsendelse af orienteringsbrev om flyttesag"
KLE = "23.00.00"
PROCEEDING_FACET = "G01"
SENSITIVITY = "Følsomme"

DOCUMENT_TITLE = "Orienteringsbrev om flyttesag"

DEPARTMENT = Department(
        id=70403,
        name="Folkeregister og Sygesikring",
        user_key="4BFOLKEREG"
)

SECURITY_DEPARTMENT = Department(
        id=818485,
        name="Borgerservice",
        user_key="4BBORGER"
)
