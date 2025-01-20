import uuid
from typing import BinaryIO
from datetime import datetime

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

from itk_dev_shared_components.kmd_nova import nova_cases, nova_documents
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess
from itk_dev_shared_components.kmd_nova.nova_objects import NovaCase, CaseParty, Document

from robot_framework import config


def get_access(orchestrator_connection: OrchestratorConnection) -> NovaAccess:
    """Return a nova accesstoken.
    """
    nova_credentials = orchestrator_connection.get_credential(config.NOVA_API)
    return NovaAccess(nova_credentials.username, nova_credentials.password)


def create_case(ident: str, name: str, eflyt_sag: str, nova_access: NovaAccess) -> NovaCase:
    """Create a Nova case based on email data.

    Args:
        ident: The CPR we are looking for
        name: The name of the person we are looking for
        data_dict: A dictionary object containing the data from the case
        nova_access: An access token for accessing the KMD Nova API

    Returns:
        New NovaCase with data defined
    """

    case_party = CaseParty(
        role="Primær",
        identification_type="CprNummer",
        identification=ident,
        name=name,
        uuid=None
    )

    case = NovaCase(
        uuid=str(uuid.uuid4()),
        title=f"{config.CASE_HEADLINE} for eFlyt sag {eflyt_sag}",
        case_date=datetime.now(),
        progress_state='Opstaaet',
        case_parties=[case_party],
        kle_number=config.KLE,
        proceeding_facet=config.PROCEEDING_FACET,
        sensitivity=config.SENSITIVITY,
        caseworker=config.CASEWORKER,
        responsible_department=config.DEPARTMENT,
        security_unit=config.SECURITY_DEPARTMENT
    )

    nova_cases.add_case(case, nova_access)
    case = nova_cases.get_case(case.uuid, nova_access)
    return case


def upload_document(case: NovaCase, nova_access: NovaAccess, file: BinaryIO, file_name: str):
    document_uuid = nova_documents.upload_document(file, file_name, nova_access)
    document = Document(
        uuid=document_uuid,
        title=config.DOCUMENT_TITLE,
        sensitivity="Følsomme",
        document_type="Udgående",
        description="Dokument til orientering om godkendelse af flyttesag i eFlyt",
        approved=True
    )
    nova_documents.attach_document_to_case(case.uuid, document, nova_access, config.SECURITY_DEPARTMENT.id, config.SECURITY_DEPARTMENT.name)
