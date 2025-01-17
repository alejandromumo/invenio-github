# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Various utility functions."""

import json
import yaml

from datetime import datetime
from operator import itemgetter

import dateutil.parser
import pytz
import requests
import six
from flask import current_app
from github3 import repository
from werkzeug.utils import import_string

from .errors import CustomGitHubMetadataError

def utcnow():
    """UTC timestamp (with timezone)."""
    return datetime.now(tz=pytz.utc)


def iso_utcnow():
    """UTC ISO8601 formatted timestamp."""
    return utcnow().isoformat()


def parse_timestamp(x):
    """Parse ISO8601 formatted timestamp."""
    dt = dateutil.parser.parse(x)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    return dt


def get_extra_metadata(gh, owner, repo_name, ref):
    """Get the metadata file."""
    try:
        content = gh.repository(owner, repo_name).file_contents(
            path=current_app.config['GITHUB_METADATA_FILE'], ref=ref
        )
        if not content:
            # File does not exists in the given ref
            return {}
        return json.loads(content.decoded.decode('utf-8'))
    except ValueError:
        raise CustomGitHubMetadataError(
            file=current_app.config['GITHUB_METADATA_FILE'])


def get_citation_metadata(gh, owner, repo_name, ref, release):
    """Get the metadata file."""
    try:
        content = gh.repository(owner, repo_name).file_contents(
            path=current_app.config['GITHUB_CITATION_FILE'], ref=ref
        )
        if not content:
            # File does not exists in the given ref
            return {}
        data = yaml.safe_load(content.decoded.decode('utf-8'))
        citation_schema = \
            current_app.config.get('GITHUB_CITATION_METADATA_SCHEMA')
        data, errors = citation_schema().load(data)
        # TODO: Refactor error storage
        for key in errors:
            errors[key] = str(errors[key])
        if release.errors and errors:
            release.errors['CITATION.cff'] = errors
        elif errors:
            release.errors = {"CITATION.cff": errors}
        return data
    except ValueError:
        raise CustomGitHubMetadataError(
            file=current_app.config['GITHUB_CITATION_FILE'])



def get_owner(gh, owner):
    """Get owner of repository as a creator."""
    try:
        u = gh.user(owner)
        name = u.name or u.login
        company = u.company or ''
        return [dict(name=name, affiliation=company)]
    except Exception:
        return None


def get_contributors(gh, repo_id):
    """Get list of contributors to a repository."""
    try:
        contributors_iter = gh.repository_with_id(repo_id).contributors()
        contributors = list(contributors_iter)
        if contributors_iter.last_status == 200:

            def get_author(contributor):
                r = requests.get(contributor['url'])
                if r.status_code == 200:
                    data = r.json()
                    return dict(
                        name=(data['name'] if 'name' in data and data['name']
                              else data['login']),
                        affiliation=data.get('company') or '',
                    )
            # Sort according to number of contributions
            contributors = sorted(
                contributors,
                key=lambda x: x.as_dict()['contributions'],
                reverse=True)
            contributors = [get_author(x.as_dict()) for x in contributors[:30]
                            if x.as_dict()['type'] == 'User']
            contributors = filter(lambda x: x is not None, contributors)
            return contributors
    except Exception:
        return None


def obj_or_import_string(value, default=None):
    """Import string or return object.

    :params value: Import path or class object to instantiate.
    :params default: Default object to return if the import fails.
    :returns: The imported object.
    """
    if isinstance(value, six.string_types):
        return import_string(value)
    elif value:
        return value
    return default
