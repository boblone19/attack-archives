import argparse
import shutil
import os
import tqdm
import re
import git
import json
# STATIC PROPERTIES
# the route for previous versions to be saved under.
previous_route = "previous"
# I'm doing spaces here for readability with symbol characters. 
# The strings will get stripped of whitespace.
# These get compiled into a regex string

allowed_in_link = "".join(list(map(lambda s: s.strip(), [
    "   -   ", 
    "   ?   ",
    "   \w   ",
    "   \\   ",
    "   $   ",
    "   \.   ",
    "   !   ",
    "   \*   ",
    "   '   ",
    "   ()   ",
    "   /    ",
]))) 


def replace_links(filepath, version_name, version_displayname):
    """In the given file, replace the in-site links to reference 
       the correct previous version
    """

    # read file contents
    with open(filepath, mode="r", encoding='utf8') as html:
        html_str = html.read()

    # foramt of the destination links, e.g /previous/oct2018/...
    dest_link_format = f"/{previous_route}/{version_name}\g<1>"

    def substitute(prefix, html_str):
        fromstr = f"{prefix}=[\"']([{allowed_in_link}]+)[\"']"
        tostr = f'{prefix}="{dest_link_format}"'
        return re.sub(fromstr, tostr, html_str)

    html_str = substitute("src", html_str)
    html_str = substitute("href", html_str)


    # add the previous versions header
    html_str = html_str.replace("<!-- !previous versions banner! -->", (\
                '<div class="container-fluid version-banner">'\
                '<div class="icon-inline baseline mr-1">'\
               f'<img src="/{previous_route}/{version_name}/theme/images/icon-warning-24px.svg">'\
                '</div>This is a preserved version of the site that was '\
               f'live between {version_displayname["start"]} and {version_displayname["end"]}. '\
                '<a href="/resources/previous-versions/">'\
                'See other versions</a> or <a href="/">'\
                'the current version</a>.</div>'))
    # replace previous versions link in dropdown
    html_str = html_str.replace(f"/{previous_route}/{version_name}/resources/previous-versions/", "/resources/previous-versions/")
    # replace changelog link in dropdown
    html_str = html_str.replace(f"/{previous_route}/{version_name}/resources/updates/", "/resources/updates/")
    # overwrite with updated html
    with open(filepath, mode="w", encoding='utf8') as updated_html:
        updated_html.write(html_str)


def preserve(version_name, version_displayname, changelog):
    """preserve the current version on github as a named previous version. """

    print("preserving current version under route '" + version_name + \
          "' with display name '" + str(version_displayname) + "'")
    
    dest = version_name

    # handle replace
    if os.path.exists(dest):
        print("\t- previous version exists with this name already: deleting previous version... ", end="", flush=True)
        shutil.rmtree(dest)
        print("done")
    

    print("\t- cloning attack-website github repo... ", end="", flush=True)
    git.Repo.clone_from("https://github.com/mitre-attack/attack-website.git",dest)
    print("done")
    # we don't want the cloned repo to use its own version control so 
    # remove the .git folder
    print("\t- removing .git from cloned repo... ", end="", flush=True)
    gitpath = os.path.join(dest, ".git")
    shutil.rmtree(gitpath)
    print("done")
    # remove cname
    print("\t- removing CNAME... ", end="", flush=True)
    cname = os.path.join(dest, "CNAME")
    os.remove(cname)
    print("done")
    
    # remove previous versions from this previous version
    preserved_previous_path = os.path.join(dest, previous_route)
    if os.path.exists(preserved_previous_path):
        print(f"\t- removing '{previous_route}' folder from preserved version to prevent recursive previous versions... ", end="", flush=True)
        shutil.rmtree(preserved_previous_path)
        print("done")
    else:
        print(f"\t- no '{previous_route}' folder to remove from from preserved version")
    
    previous_versions_list_path = os.path.join(dest, "resources", \
                                                          "previous-versions")
    if os.path.exists(previous_versions_list_path):
        print("\t- removing previous-versions page...", end="", flush=True)    
        shutil.rmtree(previous_versions_list_path)
        print("done")

    # ditto for changelog
    changelog_path = os.path.join(dest, "resources", "updates")
    if os.path.exists(changelog_path):
        print("\t- removing updates page...", end="", flush=True)    
        shutil.rmtree(changelog_path)
        print("done")

    # parse and replace content links
    print("\t- replacing links... ", end="", flush=True)

    for directory, _, files in tqdm.tqdm(os.walk(dest), \
                                                  desc="\t- replacing links"):
        for filename in filter(lambda f: f.endswith(".html"), files):
            filepath = os.path.join(directory, filename)
            replace_links(filepath, version_name, version_displayname)

    # replace site_base_url in search.js
    print("\t- replacing 'site_base_url' in search.js... ",end="", flush=True)
    search_file_path = os.path.join(dest, "theme", "scripts", "search.js")
    
    with open(search_file_path, mode="r", encoding='utf8') as search_file:
        search_contents = search_file.read()
        search_contents = re.sub('site_base_url ?= ? ""', \
                    f'site_base_url = "/{previous_route}/{version_name}"', \
                                                              search_contents)

    with open(search_file_path, mode="w", encoding='utf8') as search_file:
        search_file.write(search_contents)
    print("done")

    # update archives.json
    print("\t- updating archives.json... ", end="", flush=True)
    with open("archives.json", "r") as archives:
        archives_data = json.loads(archives.read())
    archives_data.append({
        "path": version_name,
        "date_start": version_displayname["start"],
        "date_end": version_displayname["end"],
        "changelog": changelog
    })
    with open("archives.json", "w") as archives:
        archives.write(json.dumps(archives_data, indent=4))
    print("done")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="preserve the current state of attack.mitre.org as a named previous version")
    parser.add_argument("route", type=str,
                        help="The route under which to store the previous version. Format should be monthYEAR, e.g 'january1970'"
    )
    parser.add_argument("date_start", type=str,
                        help="the date the current version went live in 'Month day, YEAR' format, e.g 'January 1, 1970'"
    )
    parser.add_argument("date_end", type=str,
                        help="the date the current version is being replaced in 'Month day, YEAR' format, e.g 'January 1, 1970'"
    )
    parser.add_argument("changelog", type=str,
                        help="the name of the changelog file for this version, to be found in resources/updates. Typically updates-MONTH-YEAR, e.g 'updates-january-1970'"
    )

    args = parser.parse_args()
    preserve(args.route, {"start": args.date_start, "end": args.date_end}, args.changelog)