from flask import render_template, jsonify

from i_lab_flask import app


@app.errorhandler(400)
def bad_request(e):
    return jsonify({
        'state': 400,
        'message': 'Bad Request'
    }), 400

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({
        'state': 404,
        'message': 'No data found, please chech your input and try again.'
    }), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({
        'state': 500,
        'message': 'Internal Server Error'
    }), 500