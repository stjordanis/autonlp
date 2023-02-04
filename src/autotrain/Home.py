import re

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, AgGridTheme, ColumnsAutoSizeMode, GridOptionsBuilder

from autotrain.project import Project
from autotrain.tasks import NLP_TASKS, TABULAR_TASKS, VISION_TASKS
from autotrain.utils import get_user_token, user_authentication


def verify_project_name(project_name):
    if project_name == "":
        st.error("Project name cannot be empty")
        return False
    if len(project_name) > 50:
        st.error("Project name cannot be longer than 50 characters")
        return False
    pattern = "^[A-Za-z0-9-]*$"
    if not re.match(pattern, project_name):
        st.error("Project name can only contain letters, numbers and hyphens")
        return False
    user_token = get_user_token()
    if user_token is None:
        st.error("You need to be logged in to create a project. Please login using `huggingface-cli login`")
        return False
    return True


def _app():
    df = pd.read_csv("https://raw.githubusercontent.com/fivethirtyeight/data/master/airline-safety/airline-safety.csv")
    AgGrid(df)


def app():  # username, valid_orgs):
    user_token = get_user_token()
    if user_token is None:
        st.error("You need to be logged in to create a project. Please login using `huggingface-cli login`")
        return
    user_info = user_authentication(token=user_token)
    username = user_info["name"]
    user_can_pay = user_info["canPay"]

    orgs = user_info["orgs"]
    valid_orgs = [org for org in orgs if org["canPay"] is True]
    valid_orgs = [org for org in valid_orgs if org["roleInOrg"] in ("admin", "write")]
    valid_orgs = [org["name"] for org in valid_orgs]

    if user_can_pay is False and len(valid_orgs) == 0:
        st.error(
            "Please attach a CC to your account or join an organization with a CC attached to it to create a project"
        )
        return

    who_is_training = [username] + valid_orgs

    col1, col2 = st.columns(2)
    with col1:
        autotrain_username = st.selectbox("Who is training?", who_is_training)
    with col2:
        project_name = st.text_input("Project name", "my-project")

    col1, col2 = st.columns(2)
    with col1:
        project_type = st.selectbox(
            "Project Type",
            [
                "Natural Language Processing",
                "Computer Vision",
                "Tabular",
            ],
        )
    with col2:
        if project_type == "Natural Language Processing":
            task = st.selectbox("Task", list(NLP_TASKS.keys()))
        elif project_type == "Computer Vision":
            task = st.selectbox("Task", list(VISION_TASKS.keys()))
        elif project_type == "Tabular":
            task = st.selectbox("Task", list(TABULAR_TASKS.keys()))

    model_choice = st.selectbox("Model choice", ["AutoTrain", "HuggingFace Hub"])
    hub_model = None
    if model_choice == "HuggingFace Hub":
        hub_model = st.text_input("Model name", "bert-base-cased")

    col1, col2 = st.columns(2)
    with col1:
        training_data = st.file_uploader("Training data", type=["csv", "jsonl"], accept_multiple_files=True)
    with col2:
        validation_data = st.file_uploader("Validation data", type=["csv", "jsonl"], accept_multiple_files=True)

    st.sidebar.markdown("### Parameters")
    if model_choice == "AutoTrain":
        st.sidebar.markdown("Parameters are selected automagically for AutoTrain models")
    else:
        learning_rate = st.sidebar.number_input("Learning rate", min_value=0.0, max_value=1.0, value=0.001)
        batch_size = st.sidebar.number_input("Batch size", min_value=1, max_value=1000, value=32)
        epochs = st.sidebar.number_input("Epochs", min_value=1, max_value=1000, value=10)
        max_seq_length = st.sidebar.number_input("Max sequence length", min_value=1, max_value=1000, value=128)
        add_job = st.sidebar.button("Add job")
        delete_all_jobs = st.sidebar.button("Delete all jobs")

        if add_job:
            if "jobs" not in st.session_state:
                st.session_state.jobs = []
            st.session_state.jobs.append(
                {
                    "learning_rate": learning_rate,
                    "batch_size": batch_size,
                    "epochs": epochs,
                    "max_seq_length": max_seq_length,
                    # "learning_rate2": learning_rate,
                    # "batch_size2": batch_size,
                    # "epochs2": epochs,
                    # "max_seq_length2": max_seq_length,
                    # "learning_rate3": learning_rate,
                    # "batch_size3": batch_size,
                    # "epochs3": epochs,
                    # "max_seq_length3": max_seq_length,
                }
            )

        if delete_all_jobs:
            st.session_state.jobs = []

    if "jobs" in st.session_state:
        if len(st.session_state.jobs) > 0:
            df = pd.DataFrame(st.session_state.jobs)
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_default_column(
                cellStyle={"color": "black", "font-size": "12px"},
                suppressMenu=True,
                wrapHeaderText=True,
                autoHeaderHeight=True,
            )
            gb.configure_selection(selection_mode="multiple", use_checkbox=True)
            custom_css = {
                ".ag-header-cell-text": {"font-size": "12px", "text-overflow": "revert;", "font-weight": 700},
                # ".ag-theme-streamlit": {"transform": "scale(0.8)", "transform-origin": "0 0"},
            }
            gridOptions = gb.build()
            ag_resp = AgGrid(
                df,
                gridOptions=gridOptions,
                custom_css=custom_css,
                # allow_unsafe_jscode=True,
                columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
                theme=AgGridTheme.STREAMLIT,  # Only choices: AgGridTheme.STREAMLIT, AgGridTheme.ALPINE, AgGridTheme.BALHAM, AgGridTheme.MATERIAL
                # width='100%',
            )
            ag_resp_sel = ag_resp["selected_rows"]
            delete_selected_jobs = st.button("Delete selected jobs")

            if ag_resp_sel:
                selected_rows = [
                    int(ag_resp_sel[i]["_selectedRowNodeInfo"]["nodeId"]) for i in range(len(ag_resp_sel))
                ]
                if delete_selected_jobs:
                    st.session_state.jobs = [
                        job for i, job in enumerate(st.session_state.jobs) if i not in selected_rows
                    ]

    create_project_button = st.button("Create Project")

    if create_project_button:
        if not verify_project_name(project_name):
            return
        project = Project(token=user_token)
        project.create(
            name=project_name,
            username=autotrain_username,
            task=task,
            language="en",
            max_models=1,
            hub_model=hub_model,
        )


if __name__ == "__main__":
    app()