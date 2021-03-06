"""
DRS Registration resource package.
Copyright (c) 2018 Qualcomm Technologies, Inc.
 All rights reserved.
 Redistribution and use in source and binary forms, with or without modification, are permitted (subject to the
 limitations in the disclaimer below) provided that the following conditions are met:
 * Redistributions of source code must retain the above copyright notice, this list of conditions and the following
 disclaimer.
 * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
 disclaimer in the documentation and/or other materials provided with the distribution.
 * Neither the name of Qualcomm Technologies, Inc. nor the names of its contributors may be used to endorse or promote
 products derived from this software without specific prior written permission.
 NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY THIS LICENSE. THIS SOFTWARE IS PROVIDED BY
 THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
 TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 POSSIBILITY OF SUCH DAMAGE.
"""
import json
import uuid

from flask import Response, request
from flask_restful import Resource
from marshmallow import ValidationError

from app import app, db
from app.api.v1.helpers.error_handlers import REG_NOT_FOUND_MSG
from app.api.v1.helpers.response import MIME_TYPES, CODES
from app.api.v1.helpers.utilities import Utilities
from app.api.v1.models.regdetails import RegDetails
from app.api.v1.models.regdevice import RegDevice
from app.api.v1.models.regdocuments import RegDocuments
from app.api.v1.schema.devicedetails import DeviceDetailsSchema
from app.api.v1.schema.regdetails import RegistrationDetailsSchema
from app.api.v1.schema.regdetailsupdate import RegistrationDetailsUpdateSchema
from app.api.v1.schema.regdocuments import RegistrationDocumentsSchema


class RegistrationRoutes(Resource):
    """Class for handling Registration Requests routes."""

    @staticmethod
    def get(reg_id=None):
        """GET method handler, returns registration requests."""
        try:
            schema = RegistrationDetailsSchema()
            if reg_id:
                if not reg_id.isdigit() or not RegDetails.exists(reg_id):
                    return Response(json.dumps(REG_NOT_FOUND_MSG), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                    mimetype=MIME_TYPES.get("APPLICATION_JSON"))

                response = RegDetails.get_by_id(reg_id)
                response = schema.dump(response).data
            else:
                response = RegDetails.get_all()
                response = schema.dump(response, many=True).data
            return Response(json.dumps(response), status=CODES.get("OK"),
                            mimetype=MIME_TYPES.get("APPLICATION_JSON"))
        except Exception as e:
            app.logger.exception(e)
            error = {
                'message': ['Failed to retrieve response, please try later']
            }
            return Response(json.dumps(error), status=CODES.get('INTERNAL_SERVER_ERROR'),
                            mimetype=MIME_TYPES.get('APPLICATION_JSON'))
        finally:
            db.session.close()

    @staticmethod
    def post():
        """POST method handler, creates registration requests."""
        tracking_id = uuid.uuid4()
        try:
            args = RegDetails.curate_args(request)
            schema = RegistrationDetailsSchema()
            file = request.files.get('file')
            validation_errors = schema.validate(args)
            if validation_errors:
                return Response(json.dumps(validation_errors), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                mimetype=MIME_TYPES.get("APPLICATION_JSON"))
            if file:
                response = Utilities.store_file(file, tracking_id)
                if response:
                    return Response(json.dumps(response), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                    mimetype=MIME_TYPES.get("APPLICATION_JSON"))
                response = Utilities.process_reg_file(file.filename, tracking_id, args)
                if isinstance(response, list):
                    response = RegDetails.create(args, tracking_id)
                else:
                    return Response(json.dumps(response), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                    mimetype=MIME_TYPES.get("APPLICATION_JSON"))
            else:
                Utilities.create_directory(tracking_id)
                response = RegDetails.create(args, tracking_id)
            db.session.commit()
            response = schema.dump(response, many=False).data
            return Response(json.dumps(response), status=CODES.get("OK"),
                            mimetype=MIME_TYPES.get("APPLICATION_JSON"))

        except Exception as e:
            db.session.rollback()
            Utilities.remove_directory(tracking_id)
            app.logger.exception(e)

            data = {
                'message': ['Registration request failed, check upload path or database connection']
            }

            return Response(json.dumps(data), status=CODES.get('INTERNAL_SERVER_ERROR'),
                            mimetype=MIME_TYPES.get('APPLICATION_JSON'))
        finally:
            db.session.close()

    @staticmethod
    def put():
        """PUT method handler, updates registration requests."""
        reg_id = request.form.to_dict().get('reg_id', None)
        if not reg_id or not reg_id.isdigit() or not RegDetails.exists(reg_id):
            return Response(json.dumps(REG_NOT_FOUND_MSG), status=CODES.get("UNPROCESSABLE_ENTITY"),
                            mimetype=MIME_TYPES.get("APPLICATION_JSON"))

        args = RegDetails.curate_args(request)
        schema = RegistrationDetailsUpdateSchema()
        file = request.files.get('file')
        reg_details = RegDetails.get_by_id(reg_id)
        try:
            tracking_id = reg_details.tracking_id
            if reg_details:
                args.update({'status': reg_details.status,
                             'reg_id': reg_details.id,
                             'processing_status': reg_details.processing_status,
                             'report_status': reg_details.report_status
                             })
            validation_errors = schema.validate(args)
            if validation_errors:
                return Response(json.dumps(validation_errors), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                mimetype=MIME_TYPES.get("APPLICATION_JSON"))
            if args.get('close_request', None) == 'True':
                response = RegDetails.close(reg_details)
                if isinstance(response, dict):
                    return Response(json.dumps(response), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                    mimetype=MIME_TYPES.get("APPLICATION_JSON"))
                else:
                    response = schema.dump(response, many=False).data
                    return Response(json.dumps(response), status=CODES.get("OK"),
                                    mimetype=MIME_TYPES.get("APPLICATION_JSON"))
            if file:
                Utilities.remove_file(reg_details.file, tracking_id)
                response = Utilities.store_file(file, tracking_id)
                if response:
                    return Response(json.dumps(response), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                    mimetype=MIME_TYPES.get("APPLICATION_JSON"))
                response = Utilities.process_reg_file(file.filename, tracking_id, args)
                if isinstance(response, list):
                    response = RegDetails.update(args, reg_details, True)
                else:
                    return Response(json.dumps(response), status=CODES.get("UNPROCESSABLE_ENTITY"),
                                    mimetype=MIME_TYPES.get("APPLICATION_JSON"))
            else:
                response = RegDetails.update(args, reg_details, False)
            db.session.commit()
            response = schema.dump(response, many=False).data
            return Response(json.dumps(response), status=CODES.get("OK"),
                            mimetype=MIME_TYPES.get("APPLICATION_JSON"))

        except Exception as e:
            db.session.rollback()
            app.logger.exception(e)

            data = {
                'message': ['Registration update request failed, check upload path or database connection']
            }

            return Response(json.dumps(data), status=CODES.get('INTERNAL_SERVER_ERROR'),
                            mimetype=MIME_TYPES.get('APPLICATION_JSON'))
        finally:
            db.session.close()


class RegSectionRoutes(Resource):
    """Class for handling Registration Section Routes."""

    @staticmethod
    def get(reg_id):
        """GET method handler, return registration sections."""
        if not reg_id or not reg_id.isdigit() or not RegDetails.exists(reg_id):
            return Response(json.dumps(REG_NOT_FOUND_MSG), status=CODES.get("UNPROCESSABLE_ENTITY"),
                            mimetype=MIME_TYPES.get("APPLICATION_JSON"))
        try:
            reg_details = RegDetails.get_by_id(reg_id)
            reg_schema = RegistrationDetailsSchema()
            doc_schema = RegistrationDocumentsSchema()
            device_schema = DeviceDetailsSchema()

            reg_device = RegDevice.get_device_by_registration_id(reg_id)
            reg_documents = RegDocuments.get_by_reg_id(reg_id)

            registration_data = reg_schema.dump(reg_details).data
            device_data = device_schema.dump(reg_device).data if reg_device else {}
            document_data = doc_schema.dump(reg_documents, many=True).data

            response = {
                'reg_details': registration_data,
                'reg_device': device_data,
                'reg_docs': document_data
            }

            return Response(json.dumps(response), status=CODES.get("OK"),
                            mimetype=MIME_TYPES.get("APPLICATION_JSON"))
        except Exception as e:
            app.logger.exception(e)

            data = {
                'message': ['Registration request failed, check upload path or database connection']
            }

            return Response(json.dumps(data), status=CODES.get('INTERNAL_SERVER_ERROR'),
                            mimetype=MIME_TYPES.get('APPLICATION_JSON'))
        finally:
            db.session.close()
