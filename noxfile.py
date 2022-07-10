import os
import webbrowser
import nox


@nox.session
def test(session: nox.Session) -> None:
    session.install('pytest')
    session.run('pytest')


@nox.session
def docs(session: nox.Session) -> None:
    # ~ Installing the doc requirements
    session.install('-r', 'requirements.txt')
    session.install('-r', 'docs/requirements.txt')

    # ~ Removing previous artifacts
    if os.path.exists('docs/modules.rst'):
        session.run('rm', '-f', 'docs/modules.rst')

    # ~ Building the docs
    session.run('sphinx-apidoc', '-o', 'docs', 'pycomex')
    session.run('sphinx-build', 'docs', 'docs/build/html')


@nox.session
def serve_docs(session: nox.Session) -> None:
    url = 'docs/build/html/index.html'
    webbrowser.open(url)
