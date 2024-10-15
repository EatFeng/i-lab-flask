from flask import jsonify
from i_lab_flask import app
from constants import StatusCodes


@app.errorhandler(400)
def bad_request(e):
    return jsonify({
        'state': StatusCodes.BAD_REQUEST,
        'message': 'Bad Request'
    }), StatusCodes.BAD_REQUEST

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({
        'state': StatusCodes.NOT_FOUND,
        'message': 'No data found, please chech your input and try again.'
    }),StatusCodes.NOT_FOUND

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({
        'state': StatusCodes.INTERNAL_SERVER_ERROR,
        'message': ' Server Error'
    }), StatusCodes.INTERNAL_SERVER_ERROR

# 自定义异常类
class CustomError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
