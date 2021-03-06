# -*- coding: utf-8 -*-
import sys
import os
import py
import pytz
import logging
from git import Repo
from datetime import datetime
from jinja2 import Environment, PackageLoader, select_autoescape


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
log.addHandler(ch)


def get_template():
    env = Environment(
        loader=PackageLoader('updatechangelog', 'templates'),
        autoescape=select_autoescape(['txt'])
    )

    return env.get_template('header.txt')


def main():
    repo_path = py.path.local(os.getcwd()) / 'salt-packaging'
    repo = Repo(repo_path.strpath)

    commit = repo.commit('HEAD')

    lastrevision = ''
    lastrevision_file = py.path.local('_lastrevision')
    if lastrevision_file.isfile():
        lastrevision = lastrevision_file.read().strip()

    lastrevision = lastrevision or commit.hexsha

    if not repo.git.merge_base(lastrevision, commit.hexsha):
        log.error((
            "%s is not an ancestor of %s. "
            "Maybe force-push was used. "
            "Fix _lastrevision reference.") % (lastrevision, commt.hexsha))
        sys.exit(1)

    if "[skip]" in commit.message:
        sys.exit(0)

    existing_patches = set(
        [
            py.path.local(it.path).basename
            for it in repo.commit(lastrevision).tree['salt']
            if it.path.endswith(".patch")
        ]
    )

    current_patches = set(
        [
            py.path.local(it.path).basename
            for it in repo.commit('HEAD').tree['salt']
            if it.path.endswith(".patch")
        ]
    )

    deleted = existing_patches.difference(current_patches)
    added = current_patches.difference(existing_patches)
    modified = set(
        [
            py.path.local(it.a_path).basename
            for it in repo.commit("HEAD").diff(lastrevision)
            if it.a_path.endswith(".patch")
        ]
    ).difference(added.union(deleted))

    template = get_template()

    current_dt = datetime.now().replace(tzinfo=pytz.utc)

    lastrevision_commit = repo.commit(lastrevision)
    ref = repo.commit("HEAD")
    messages = []
    while ref.hexsha != repo.commit(lastrevision).hexsha:
        messages.append(ref.message.encode('utf8'))
        ref = repo.commit("%s^" % ref.hexsha)

    if not messages:
        log.info("Nothing new.")
        sys.exit(0)

    changelog_entry = template.render(
        messages=messages,
        name=commit.author.name,
        email=commit.author.email,
        added=added,
        modified=modified,
        deleted=deleted,
        datetime=current_dt.strftime("%a %b %-d %X %Z %Y")
    )

    try:
        with open('salt.changes', 'r+') as f:
            content = f.read()
            f.seek(0, 0)
            f.write(changelog_entry.encode('utf-8'))
            f.write('\n')
            f.write(content)
    except Exception:
        log.error("Unable to write the changelog.")
        sys.exit(1)
    else:
        with open('_lastrevision', 'wb') as f:
            f.write(commit.hexsha)
