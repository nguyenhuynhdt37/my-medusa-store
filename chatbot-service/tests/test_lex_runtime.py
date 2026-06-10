from app.clients.lex_runtime import _is_lex_conflict


class ConflictLikeError(Exception):
    response = {"Error": {"Code": "ConflictException"}}


class OtherError(Exception):
    response = {"Error": {"Code": "ThrottlingException"}}


def test_is_lex_conflict_reads_botocore_error_code():
    assert _is_lex_conflict(ConflictLikeError()) is True
    assert _is_lex_conflict(OtherError()) is False
