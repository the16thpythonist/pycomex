
Releasing new version
---------------------

.. code-block:: console

    poetry lock
    poetry version [ major | minor | patch ]
    poetry build
    poetry publish --username='...' --password='...'
    git commit -a -m "..."
    git push origin master
