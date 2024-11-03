import json
import threading

from flask import Flask, render_template, request, jsonify, Response
from pathlib import Path
import pygit2
import requests
import time
import sqlite3

import utils
import settings

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


def check_answer(answer, right_answer):
    return answer.strip() == right_answer.strip()


def check_page_content(content, right_answer):
    return content.strip() == right_answer.strip()


@app.route('/apply_requirements', methods=['POST'])
def apply_requirements():
    data = request.get_json()
    settings.routes = data.get('routes', [])
    return jsonify({"message": "Files updated successfully"}), 200


@app.route('/check_solution_from_github')
def check_solution_from_github():
    def generate():
        data = [[] for _ in range(len(settings.repositories))]
        for repo_idx, repo_url in enumerate(settings.repositories):
            local_path = './cloned_repository'

            utils.delete_folder(local_path)

            local_path = './cloned_repository'
            pygit2.clone_repository(repo_url, local_path)

            image_name = 'image1'
            container_name = 'container1'

            dockerfile_path = "./cloned_repository/Dockerfile"

            data[repo_idx] = {'routes_checking': [[f"'{filename}'", 'NS'] for filename in settings.files_that_should_exist],
                              'files_checking': [[f'Test {i + 1}', 'NS'] for i in range(len(settings.routes))]}

            #files_checking_results = [[f"'{filename}'", 'NS'] for filename in settings.files_that_should_exist]
            #checking_results = [[f'Test {i + 1}', 'NS'] for i in range(len(settings.routes))]

            yield f"data: {json.dumps({'data': data})}\n\n"

            # Checking for presence/absence of different files in the repository
            for i, filename in enumerate(settings.files_that_should_exist):
                file_path = f'./cloned_repository/{filename}'
                path = Path(file_path)
                if path.is_file():
                    data[repo_idx]['routes_checking'][i][1] = 'OK'
                else:
                    data[repo_idx]['routes_checking'][i][1] = "Doesn't exist"

            #yield f"data: {json.dumps({'routes_checking': checking_results, 'files_checking': files_checking_results})}\n\n"
            yield f"data: {json.dumps({'data': data})}\n\n"

            # If there is no Dockerfile program will try to run main.py from the cloned repository
            if not Path(dockerfile_path).is_file():
                print(f'Dockerfile is not found. Trying to run main.py from {local_path}/')
                try:
                    with open(f'./cloned_repository/main.py', 'r', encoding='utf-8') as f:
                        code = f.read()
                    t1 = threading.Thread(target=lambda: exec(code))
                    t1.start()
                except:
                    pass
            else:
                print('Dockerfile found')
                utils.build_docker_container(dockerfile_path='./cloned_repository/', image_name=image_name,
                                             container_name=container_name)

            time.sleep(5)  # waiting for program to start

            for i, (route, right_answer) in enumerate(settings.routes):
                print(f'Test {i + 1}')
                try:
                    url = f"http://localhost:8080{route}"
                    response = requests.get(url)
                    content = response.text
                    print(f'\troute: {route}')
                    print(f'\tcontent: {content}')
                    print(f'\tright answer: {right_answer}')
                except Exception as e:
                    print(e)
                    # checking_results.append([f'Test {i + 1}', 'RT'])
                else:
                    if check_page_content(str(content), right_answer):
                        data[repo_idx]['files_checking'][i][1] = 'OK'
                    else:
                        data[repo_idx]['files_checking'][i][1] = 'WA'
                #yield f"data: {json.dumps({'routes_checking': checking_results, 'files_checking': files_checking_results})}\n\n"
                yield f"data: {json.dumps({'data': data})}\n\n"

            print('Checking results:')
            print(data[repo_idx]['files_checking'])
            print()

            print('Deleting a container...')
            container = utils.client.containers.get(container_name)
            container.stop()
            container.remove()

            print('Deleting an image...')
            image = utils.client.images.get(image_name)
            utils.client.images.remove(image.id)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/dynamic_fields/<name>', methods=['POST'])
def dynamic_fields(name):
    match name:
        case 'files':
            data = request.get_json()
            settings.files_that_should_exist = data.get('data', [])
            records = [(i,) for i in data.get('data', [])]
            utils.executemany_sql_in_new_connection("INSERT INTO Files (name) VALUES (?)", records)
            return jsonify({"message": "Files updated successfully"}), 200
        case 'repositories':
            data = request.get_json()
            settings.repositories = data.get('data', [])
            records = [(i,) for i in data.get('data', [])]
            utils.executemany_sql_in_new_connection("INSERT INTO Repositories (repository_link) VALUES (?)", records)
            print('settings.repositories', settings.repositories)
            return jsonify({"message": "Files updated successfully"}), 200
        case _:
            return jsonify({"error": "Invalid name provided"}), 404


if __name__ == '__main__':
    utils.execute_sql_file('./web_checker_for_exams/sql/schema.sql')

    app.run(port=8081)
