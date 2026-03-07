from efarmogi import vasi, diaxeiristh_syndeshs
from flask_login import UserMixin

@diaxeiristh_syndeshs.user_loader
def fortwsh_xrhsth(xrhsths_id):
    return Xrhsths.query.get(int(xrhsths_id))

class Xrhsths(vasi.Model, UserMixin):
    __tablename__ = 'xrhstes'
    id = vasi.Column(vasi.Integer, primary_key=True)
    onoma_xrhsth = vasi.Column(vasi.String(20), unique=True, nullable=False)
    email = vasi.Column(vasi.String(120), unique=True, nullable=False)
    kwdikos = vasi.Column(vasi.String(60), nullable=False)

    def __repr__(self):
        return f"Xrhsths('{self.onoma_xrhsth}', '{self.email}')"