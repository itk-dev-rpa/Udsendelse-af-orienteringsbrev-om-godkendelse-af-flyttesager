"""This module contains functions for using the Nova API."""

import uuid
from typing import BinaryIO
from datetime import datetime

from itk_dev_shared_components.kmd_nova import nova_cases, nova_documents
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess
from itk_dev_shared_components.kmd_nova.nova_objects import NovaCase, CaseParty, Document

from robot_framework import config


def create_case(ident: str, name: str, nova_access: NovaAccess) -> NovaCase:
    """Create a Nova case based on email data.

    Args:
        ident: The CPR we are looking for
        name: The name of the person we are looking for
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
        title=config.CASE_HEADLINE,
        case_date=datetime.now(),
        progress_state='Afsluttet',
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
    """Upload document to Nova and attach to case.

    Args:
        case: NovaCase to attach document.
        nova_access: Access token for Nova.
        file: Document to upload.
        file_name: Filename for document.
    """
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
