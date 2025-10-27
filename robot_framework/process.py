"""This module contains the main process of the robot."""

import os
from datetime import datetime, timedelta
from io import BytesIO
import base64

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueStatus
from itk_dev_shared_components.eflyt import eflyt_login, eflyt_search, eflyt_case
from itk_dev_shared_components.eflyt.eflyt_case import Case
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from python_serviceplatformen.models.message import create_digital_post_with_main_document, Sender, Recipient, File
from python_serviceplatformen import digital_post
from python_serviceplatformen.authentication import KombitAccess
import hvac

from robot_framework import config
from robot_framework.custom import nova


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    kombit_access = create_kombit_access(orchestrator_connection)

    eflyt_creds = orchestrator_connection.get_credential(config.EFLYT_LOGIN)
    browser = eflyt_login.login(eflyt_creds.username, eflyt_creds.password)

    from_date = (datetime.now()-timedelta(days=5)).date()
    to_date = datetime.today().date()

    eflyt_search.search(browser, from_date=from_date, to_date=to_date, case_state="Afsluttet", case_status="Godkendt")
    cases = eflyt_search.extract_cases(browser)
    orchestrator_connection.log_info(f"Total cases found: {len(cases)}")
    cases = filter_cases(cases)
    orchestrator_connection.log_info(f"Relevant cases found: {len(cases)}")

    nova_credentials = orchestrator_connection.get_credential(config.NOVA_API)
    nova_access = NovaAccess(nova_credentials.username, nova_credentials.password)

    for case in cases:
        if not check_queue(case.case_number, orchestrator_connection):
            continue

        queue_element = orchestrator_connection.create_queue_element(config.QUEUE_NAME, case.case_number)
        orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.IN_PROGRESS)

        eflyt_search.open_case(browser, case.case_number)

        if not check_case_log(browser):
            orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE, "Springer over: Sagslog.")
            continue

        # Find data for letter
        move_date = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_GridViewMovingPersons_ctl02_lnkDateCPR").text
        address = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_stcPersonTab3_lblTiltxt").text
        cpr, name = get_main_applicant(browser)

        # Generate and send letter
        letter_file = generate_letter(name=name, address=address, move_date=move_date, case_number=case.case_number)
        b64_letter = base64.b64encode(letter_file.read()).decode()
        letter_file.seek(0)
        send_letter(cpr, b64_letter, kombit_access)

        # Save letter in Nova
        nova_case = nova.create_case(cpr, name, nova_access)
        nova.upload_document(nova_case, nova_access, letter_file, f"{config.DOCUMENT_TITLE}.pdf")
        eflyt_case.add_note(browser, f"Orienteringsbrev om godkendelse journaliseret i Nova-sag: {nova_case.case_number}")

        orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE, "Brev sendt")

        add_case_log(browser)


def filter_cases(cases: list[Case]) -> list[Case]:
    """Filter cases from the case table.

    Args:
        cases: A list of cases to filter.

    Returns:
        A list of filtered case objects.
    """
    ignored_case_types = ["Børneflytning 1", "Børneflytning 2", "Børneflytning 3", "Mindreårig", "Barn", "Udland", "Tilflytning høj vejkode"]
    filtered_cases = [
        case for case in cases
        if not any(case_type in case.case_types for case_type in ignored_case_types) and case.status == "Godkendt"
    ]

    return filtered_cases


def get_main_applicant(browser: webdriver.Chrome):
    """Find the main applicant on the case denoted with an 'A'.

    Args:
        browser: The webdriver object to perform the action.

    Raises:
        RuntimeError: If no applicant with 'A' was found.

    Returns:
        The cpr and name of the applicant.
    """
    table = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_GridViewMovingPersons")
    rows = table.find_elements(By.TAG_NAME, "tr")

    # Remove header row
    rows.pop(0)

    for row in rows:
        if row.find_element(By.XPATH, "td[2]/a[1]").text == 'A':
            cpr = row.find_element(By.XPATH, "td[2]/a[2]").text.replace("-", "")
            name = row.find_element(By.XPATH, "td[3]/a").text

            name = name.split(",")
            name = f"{name[1]} {name[0]}"

            return cpr, name

    raise RuntimeError("No main applicant found")


def generate_letter(name: str, address: str, move_date: str, case_number: str) -> BytesIO:
    """Generate a pdf letter to send.

    Args:
        name: The name of the receiver.
        address: The address of the receiver. Any line breaks will be preserved.
        date: The date the letter is sent.
        case_number: The case number in eFlyt.

    Returns:
        The PDF-file as BytesIO
    """
    file = BytesIO()
    c = canvas.Canvas(file, pagesize=A4)
    c.setFont("Helvetica", 10)

    c.drawImage("aarhus logo.png", 155*mm, 267*mm, width=49*mm, height=25*mm)

    t = c.beginText(24*mm, 247*mm)
    t.textLine(name)
    t.textLines(address)
    c.drawText(t)

    c.drawString(24*mm, 211*mm, f"Den {get_date_string()}")
    c.drawString(110*mm, 211*mm, f"Flyttesagsnr.: {case_number}")

    t = c.beginText(160*mm, 213*mm)
    t.setFont("Helvetica-Bold", 12)
    t.textLine("Aarhus Kommune")
    t.textLine("Borgerservice")
    c.drawText(t)

    t = c.beginText(160*mm, 192*mm)
    t.setFont("Helvetica-Bold", 8)
    t.textLine("Folkeregister/Sygesikring")
    t.textLine("Dokk1")
    t.textLine("Hack Kampmanns Plads 2")
    t.textLine("8000 Aarhus C")
    t.textLine("")
    t.textLine("Telefon 8940 2000")
    t.textLine("")
    t.textLine("aarhus.dk")
    c.drawText(t)

    t = c.beginText(24*mm, 195*mm)
    t.setFont("Helvetica", 10)
    t.textLine("Din anmodning om flytning til nedenstående adresse er blevet godkendt.")
    t.textLine("")
    t.textLines(address)
    t.textLine("")
    t.textLine("Flyttedato:")
    t.textLine(move_date)
    t.textLine("")
    t.textLine("Med venlig hilsen")
    t.textLine("Aarhus Folkeregister")
    c.drawText(t)

    c.showPage()
    c.save()

    file.seek(0)
    return file


def get_date_string() -> str:
    """Returns the current date as a string in the format
    "1. januar 2024".

    Returns:
        The current date as a Danish string.
    """
    months = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december"]

    d = datetime.now()

    return f"{d.day}. {months[d.month-1]} {d.year}"


def create_kombit_access(orchestrator_connection: OrchestratorConnection) -> KombitAccess:
    """Get the certificate from Hashicorp Vault and create a KombitAccess object.

    Args:
        orchestrator_connection: The connection to orchestrator.

    Returns:
        A KombitAccess object.
    """
    # Access Keyvault
    vault_auth = orchestrator_connection.get_credential(config.KEYVAULT_CREDENTIALS)
    vault_uri = orchestrator_connection.get_constant(config.KEYVAULT_URI).value

    vault_client = hvac.Client(vault_uri)
    vault_client.auth.approle.login(role_id=vault_auth.username, secret_id=vault_auth.password)

    # Get certificate
    read_response = vault_client.secrets.kv.v2.read_secret_version(mount_point='rpa', path=config.KEYVAULT_PATH, raise_on_deleted_version=True)
    certificate = read_response['data']['data']['cert']
    if not certificate:
        raise RuntimeError("Unable to obtain certificate from vault")

    # Because KombitAccess requires a file, we save the certificate
    certificate_path = "certificate.pem"
    with open(certificate_path, 'w', encoding='utf-8') as cert_file:
        cert_file.write(certificate)

    return KombitAccess("55133018", certificate_path)


def send_letter(cpr: str, b64_letter: str, kombit_access: KombitAccess):
    """Send a letter using Digital Post.

    Args:
        cpr: Recipient ID.
        b64_letter: Letter as byte string.
        kombit_access: Acces token for Kombit Serviceportal.
    """
    message = create_digital_post_with_main_document(
            label="Godkendelse af flyttesag",
            recipient=Recipient(
                recipientID=cpr,
                idType="CPR",
            ),
            sender=Sender(
                senderID="55133018",
                idType="CVR",
                label="Aarhus Kommune"
            ),
            files=[
                File(
                    filename="Brev.pdf",
                    language="da",
                    encodingFormat="application/pdf",
                    content=b64_letter
                )
            ]
        )

    digital_post.send_message("Digital Post", message, kombit_access)


def add_case_log(browser: webdriver.Chrome):
    """Add a log to the caselog about the letter being sent.

    Args:
        browser: The webdriver object to perform the action.
    """
    eflyt_case.change_tab(browser, 2)

    activity_select = Select(browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_sgcPersonTab_ddlselAktivitet"))
    activity_select.select_by_visible_text("Afsendt")

    browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_sgcPersonTab_txtHaendt").send_keys(datetime.today().strftime("%d-%m-%Y"))
    browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_sgcPersonTab_txtHandling").send_keys(config.NOTE_TEXT)
    browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_sgcPersonTab_btnAddSagslog").click()


def check_case_log(browser: webdriver.Chrome) -> bool:
    """Check the case log to see if the robot has already handled this case.

    Args:
        browser: The webdriver object to perform the action.

    Returns:
        True if the case should be handled. False if the case should be skipped.
    """
    eflyt_case.change_tab(browser, 2)
    browser.implicitly_wait(0.2)
    log_table = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_sgcPersonTab_GridViewSagslog")
    rows = log_table.find_elements(By.CSS_SELECTOR, "span[id$=_lblHandling]")

    for row in rows:
        if row.text in config.NOTE_TEXT:
            return False

    return True


def check_queue(case_number: str, orchestrator_connection: OrchestratorConnection) -> bool:
    """Check if a case has been handled before by checking the job queue i Orchestrator.

    Args:
        case_number: The case number to check.
        orchestrator_connection: The connection to Orchestrator.

    Return:
        bool: True if the element should be handled, False if it should be skipped.
    """
    queue_elements = orchestrator_connection.get_queue_elements(queue_name=config.QUEUE_NAME, reference=case_number)

    if len(queue_elements) == 0:
        return True

    # If the case has been tried more than once before skip it
    if len(queue_elements) > 1:
        orchestrator_connection.log_info("Skipping: Case has failed in the past.")
        return False

    # If it has been marked as done, skip it
    if queue_elements[0].status == QueueStatus.DONE:
        orchestrator_connection.log_info("Skipping: Case already marked as done.")
        return False

    return True


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("Eflyt Test", conn_string, crypto_key, "")
    process(oc)
