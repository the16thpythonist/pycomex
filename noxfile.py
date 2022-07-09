import nox


@nox.session
def test(session: nox.Session) -> None:
    session.install('pytest')
    session.run('pytest')

