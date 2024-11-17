from app import Creator, GitHubSponsorsPaymentMethod


def test_github_payment_method(test_db_session):
    creator = Creator(
        slug="python-software-foundation",
        display_name="Python Software Foundation",
        web_url="https://python.org/psf-landing",
    )
    gh = GitHubSponsorsPaymentMethod(
        github_id=1525981,
        github_login="python",
        creator=creator,
    )
    test_db_session.add(creator)
    test_db_session.add(gh)
    test_db_session.commit()

    assert gh.type == "payment_methods_github_sponsors"
    assert isinstance(gh.id, int)
    assert gh.github_id == 1525981
    assert gh.github_login == "python"
    assert gh.html_url == "https://github.com/sponsors/python"
    assert gh.creator == creator
    assert creator.payment_methods == [gh]
    assert isinstance(creator.payment_methods[0], GitHubSponsorsPaymentMethod)
