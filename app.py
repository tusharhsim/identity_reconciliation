import os
from dotenv import load_dotenv

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import or_, UniqueConstraint

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')

uri = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phoneNumber = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    linkedId = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=True)
    linkPrecedence = db.Column(db.String(10), nullable=False, default='primary')
    createdAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deletedAt = db.Column(db.DateTime, nullable=True)

    __table_args__ = (UniqueConstraint('email', 'phoneNumber', name='email_phone_uc'),)

    def __init__(self, phoneNumber=None, email=None, linkedId=None, linkPrecedence='primary'):
        self.phoneNumber = phoneNumber
        self.email = email
        self.linkedId = linkedId
        self.linkPrecedence = linkPrecedence


@app.route('/identify', methods=['POST'])
def identify():
    try:
        data = request.json
        email, phoneNumber = data.get('email'), data.get('phoneNumber')
        primary_contact, secondary_contacts = None, []

        contacts = Contact.query.filter(
            or_(Contact.email == email, Contact.phoneNumber == phoneNumber)
        ).all()

        if contacts:
            app.logger.info(f'getting in if block {contacts}')

            if linked_contact_ids := [contact.linkedId for contact in contacts if contact.linkedId is not None]:
                contacts.extend(Contact.query.filter(Contact.id.in_(linked_contact_ids)).all())
            if primary_contact_ids := [contact.id for contact in contacts if contact.linkedId is None]:
                contacts.extend(Contact.query.filter(Contact.linkedId.in_(primary_contact_ids)).all())

            primary_contact = min(contacts, key=lambda x: x.createdAt)
            for contact in contacts:
                if contact.id != primary_contact.id:
                    contact.linkedId = primary_contact.id
                    contact.linkPrecedence = 'secondary'
                    app.logger.info(f'appending {contact}')
                    secondary_contacts.append(contact)

            if ((email and email != primary_contact.email) or (phoneNumber and phoneNumber != primary_contact.phoneNumber)) \
                    and not any(sc.email == email or sc.phoneNumber == phoneNumber for sc in secondary_contacts):
                new_secondary = Contact(email=email, phoneNumber=phoneNumber, linkedId=primary_contact.id,
                                        linkPrecedence='secondary')
                db.session.add(new_secondary)
                secondary_contacts.append(new_secondary)
            db.session.commit()
        else:
            app.logger.info(f'getting in else block {contacts}')
            primary_contact = Contact(email=email, phoneNumber=phoneNumber)
            db.session.add(primary_contact)
            db.session.commit()

        response = {
            "contact": {
                "primaryContactId": primary_contact.id,
                "emails": list(set([primary_contact.email] + [sc.email for sc in secondary_contacts if sc.email])),
                "phoneNumbers": list(
                    set([primary_contact.phoneNumber] + [sc.phoneNumber for sc in secondary_contacts if sc.phoneNumber])),
                "secondaryContactIds": list(set(sc.id for sc in secondary_contacts))
            }
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)
