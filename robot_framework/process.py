"""This module contains the main process of the robot."""

import os
from datetime import datetime, timedelta
from io import BytesIO
import base64

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueStatus
from itk_dev_shared_components.eflyt import eflyt_login, eflyt_search, eflyt_case
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


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    kombit_access = create_kombit_access(orchestrator_connection)

    eflyt_creds = orchestrator_connection.get_credential(config.EFLYT_LOGIN)
    browser = eflyt_login.login(eflyt_creds.username, eflyt_creds.password)

    from_date = (datetime.now()-timedelta(days=5)).date()
    to_date = datetime.today().date()

    eflyt_search.search(browser, from_date=from_date, to_date=to_date, case_state="Afsluttet", case_status="Godkendt")
    cases = filter_cases(browser, orchestrator_connection)

    for case in cases:
        # TODO
        # queue_element = orchestrator_connection.create_queue_element(config.QUEUE_NAME)
        # orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.IN_PROGRESS)

        eflyt_search.open_case(browser, case)

        if not check_case_log(browser):
            # orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE, "Springer over: Sagslog.")
            continue

        move_date = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_GridViewMovingPersons_ctl02_lnkDateCPR").text
        address = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_stcPersonTab3_lblTiltxt").text
        cpr, name = get_main_applicant(browser)

        b64_letter = generate_letter(name=name, address=address, move_date=move_date, case_number=case)
        send_letter(cpr, b64_letter, kombit_access)

        print("Hej")

        # orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE, "Brev sendt")

        # add_case_log(browser)

    print("Hej")


def filter_cases(browser: webdriver.Chrome, orchestrator_connection: OrchestratorConnection) -> list[str]:
    """Find cases in the case list that have the status "Godkendt".
    Also filter away cases that are already 'Done' in the orchestrator queue.

    Args:
        browser: The webdriver object to perform the action.
        orchestrator_connection: The connection to Orchestrator.

    Returns:
        A list of case numbers to handle.
    """
    table = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_GridViewSearchResult")
    rows = table.find_elements(By.TAG_NAME, "tr")
    rows.pop(0)

    cases = []
    for row in rows[:10]:  # TODO
        case_status = row.find_element(By.XPATH, "td[5]").text
        if case_status != "Godkendt":
            continue

        case_number = row.find_element(By.XPATH, "td[3]").text

        if orchestrator_connection.get_queue_elements(config.QUEUE_NAME, reference=case_number, status=QueueStatus.DONE, limit=1):
            continue

        cases.append(case_number)

    return cases


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


def generate_letter(name: str, address: str, move_date: str, case_number: str) -> str:
    """Generate a pdf letter to send.

    Args:
        name: The name of the receiver.
        address: The address of the receiver. Any line breaks will be preserved.
        date: The date the letter is sent.
        case_number: The case number in eFlyt.

    Returns:
        A base 64 str representing the letter.
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

    # Convert pdf to base64
    file.seek(0)
    return base64.b64encode(file.read()).decode()


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
    log_table = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_ptFanePerson_sgcPersonTab_GridViewSagslog")
    rows = log_table.find_elements(By.CSS_SELECTOR, "span[id$=_lblHandling]")

    for row in rows:
        if row.text == config.NOTE_TEXT:
            return False

    return True


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("Eflyt Test", conn_string, crypto_key, "")
    process(oc)
