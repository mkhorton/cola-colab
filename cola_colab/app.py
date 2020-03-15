import dash
import dash_html_components as html
import dash_core_components as dcc
import plotly.express as px
import plotly.graph_objects as go
import flask
import os

from pathlib import Path
from flask_caching import Cache
from plotly.subplots import make_subplots
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from monty.serialization import loadfn
from scout_apm.flask import ScoutApm

from cola_colab.data import (
    MOST_COMMON_JOBS,
    UC_WIDE_SALARY_DF,
    PAY_TYPES,
    HUD,
    SURVEY,
    CAMPUSES,
    NET_STIPEND,
    DISCIPLINES,
)

# note to would-be code critics, this was a quick app intended as
# a one-and-done, best practices not necessairly followed --
# nevertheless, PRs gratefully received

# minimal styling
BULMA_CSS = "https://cdn.jsdelivr.net/npm/bulma@0.8.0/css/bulma.min.css"
OPEN_SANS = "https://fonts.googleapis.com/css?family=Open+Sans&display=swap"
FONT_AWESOME = "https://use.fontawesome.com/releases/v5.3.1/js/all.js"
GOOGLE_ANALYTICS = "https://www.googletagmanager.com/gtag/js?id=UA-159557337-1"

# used to store description text etc.
TEXT = loadfn("cola_colab/text.yaml")


def get_cost_of_living(percentage: float, campus: str, academic_year: int):
    """
    Get an approximate cost of living figure in USD per equation in whitepaper.
    
    Args:
        percentage (float): 0-100
        campus (str): Campus to look up rental data
        academic_year (int): Will average rental data for this year and the next, to be
            consistent with academic years
    
    Returns:
        (float) cost of living figure per month
    """

    def get_average_cost(bedroom_name: str, num_bedrooms: int):
        return 0.5 * (
            (
                HUD.loc[(campus, bedroom_name), f"{academic_year} FMR"]
                / num_bedrooms
                / (percentage / 100)
            )
            + (
                HUD.loc[(campus, bedroom_name), f"{academic_year+1} FMR"]
                / num_bedrooms
                / (percentage / 100)
            )
        )

    return (1 / 5) * (
        get_average_cost("Efficiency", 1)
        + get_average_cost("1 br", 1)
        + get_average_cost("2 br", 2)
        + get_average_cost("3 br", 3)
        + get_average_cost("4 br", 4)
    )


meta_tags = [
    {"name": "title", "content": TEXT["title"]},
    {"name": "description", "content": TEXT["preview_text"]},
    {"name": "image", "content": "https://uc-cola.herokuapp.com/assets/thumbnail.png"},
    {"name": "url", "content": "https://uc-cola.herokuapp.com"},
    {"name": "og:title", "content": TEXT["title"]},
    {"name": "og:description", "content": TEXT["preview_text"]},
    {
        "name": "og:image",
        "content": "https://uc-cola.herokuapp.com/assets/thumbnail.png",
    },
    {"name": "og:url", "content": "https://uc-cola.herokuapp.com"},
    {"name": "twitter:title", "content": TEXT["title"]},
    {"name": "twitter:description", "content": TEXT["preview_text"]},
    {
        "name": "twitter:image",
        "content": "https://uc-cola.herokuapp.com/assets/thumbnail.png",
    },
    {"name": "twitter:url", "content": "https://uc-cola.herokuapp.com"},
    {"name": "twitter:card", "content": "summary_large_image"},
    {"http-equiv": "X-UA-Compatible", "content": "IE=edge"},
    {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
]

app = dash.Dash(
    __name__,
    external_stylesheets=[BULMA_CSS, OPEN_SANS],
    external_scripts=[FONT_AWESOME, GOOGLE_ANALYTICS],
    meta_tags=meta_tags,
)
app.title = TEXT["title"]
server = app.server

# performance monitoring
ScoutApm(server)

if "REDIS_URL" in os.environ:
    cache = Cache(
        app.server,
        config={
            "CACHE_TYPE": "redis",
            "CACHE_REDIS_URL": os.environ.get("REDIS_URL", ""),
        },
    )
else:
    cache = Cache(
        app.server, config={"CACHE_TYPE": "filesystem", "CACHE_DIR": "cache-directory"}
    )

layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.H2(TEXT["title"], className="title is-2"),
                        html.H4(TEXT["authors"], className="subtitle is-4"),
                        dcc.Markdown(TEXT["affiliations"], className="content"),
                        html.Div(
                            [
                                html.H4("Introduction", className="title is-4"),
                                dcc.Markdown(TEXT["introduction"]),
                                html.Br(),
                                html.A(
                                    html.Button(
                                        [
                                            html.Span(
                                                html.I(className="fas fa-file-pdf"),
                                                className="icon",
                                            ),
                                            html.Span("Download the whitepaper"),
                                        ],
                                        className="button is-link",
                                    ),
                                    href="uc-cola-whitepaper.pdf",
                                ),
                            ],
                            className="box column is-8 content",
                        ),
                        html.Br(),
                        html.Br(),
                        html.H4("Summary Graph", className="title is-4"),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Label(
                                            "Select a campus", className="label"
                                        ),
                                        dcc.Dropdown(
                                            options=[
                                                {"label": c, "value": c}
                                                for c in CAMPUSES
                                            ],
                                            value=CAMPUSES[0],
                                            id="campus",
                                            clearable=False,
                                        ),
                                        html.Br(),
                                        html.Label(
                                            "Select discipline", className="label"
                                        ),
                                        dcc.Dropdown(
                                            options=[
                                                {
                                                    "label": discipline,
                                                    "value": discipline,
                                                }
                                                for discipline in DISCIPLINES
                                            ],
                                            value="Total",
                                            id="discipline",
                                            clearable=False,
                                        ),
                                        html.Br(),
                                        html.Label(
                                            "Define rent burden threshold",
                                            className="label",
                                        ),
                                        dcc.Slider(
                                            min=10,
                                            max=90,
                                            value=30,
                                            step=5,
                                            tooltip={
                                                "always_visible": False,
                                                "placement": "bottom",
                                            },
                                            id="cost_of_living",
                                            marks={
                                                10: "10%",
                                                30: "30%",
                                                50: "50%",
                                                70: "70%",
                                                90: "90%",
                                            },
                                        ),
                                        html.Span(
                                            "A person is rent burdened if they spend more than "
                                        ),
                                        html.Span("30", id="burden"),
                                        html.Span("% of their salary on rent."),
                                        html.Br(),
                                        html.Br(),
                                        html.Span(
                                            "Efficiency units are defined as ones in which "
                                            "the living area is not separated from the "
                                            "sleeping area."
                                        ),
                                    ],
                                    className="column is-3",
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(
                                            id="hud_graph",
                                            figure={
                                                "layout": {
                                                    "xaxis": {"visible": False},
                                                    "yaxis": {"visible": False},
                                                    "paper_bgcolor": "rgba(0,0,0,0)",
                                                    "plot_bgcolor": "rgba(0,0,0,0)",
                                                }
                                            },
                                            config={"displayModeBar": False},
                                        )
                                    ],
                                    className="column",
                                ),
                            ],
                            className="columns",
                        ),
                        html.H4(
                            "Cost-of-Living Deficit Calculator", className="title is-4"
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        dcc.Markdown(
                                            """
                                        Given the rent burden threshold defined above, we can calculate the average 
                                        cost-of-living adjustment (COLA) necessary across disciplines.
                                        """
                                        )
                                    ],
                                    className="column is-3",
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(
                                            id="deficit_graph",
                                            figure={
                                                "layout": {
                                                    "xaxis": {"visible": False},
                                                    "yaxis": {"visible": False},
                                                    "paper_bgcolor": "rgba(0,0,0,0)",
                                                    "plot_bgcolor": "rgba(0,0,0,0)",
                                                }
                                            },
                                            config={"displayModeBar": False},
                                        )
                                    ],
                                    className="column",
                                ),
                            ],
                            className="columns",
                        ),
                        # html.H4("COLA in Context", className="title is-4"),
                        html.H4("Salary Distribution", className="title is-4"),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        dcc.Markdown(
                                            "This chart allows an exploration of UC-wide student salaries against time. "
                                            "Only job titles with more than a thousand employees are shown. "
                                            "If you can supply data aggregated by campus in a computer-readable format, please "
                                            "let us know."
                                        ),
                                        html.Br(),
                                        html.Label(
                                            "Select job title(s)", className="label"
                                        ),
                                        dcc.Dropdown(
                                            options=[
                                                {"label": job, "value": job}
                                                for job in MOST_COMMON_JOBS
                                            ],
                                            value=["TEACHG ASST-GSHIP"],
                                            multi=True,
                                            clearable=False,
                                            id="job_titles",
                                        ),
                                        html.Br(),
                                        html.Label(
                                            "Select pay type", className="label"
                                        ),
                                        dcc.Dropdown(
                                            options=[
                                                {"label": job, "value": job}
                                                for job in PAY_TYPES
                                            ],
                                            value=PAY_TYPES[0],
                                            clearable=False,
                                            id="pay_type",
                                        ),
                                        html.Br(),
                                        html.Label("View year(s)", className="label"),
                                        dcc.Dropdown(
                                            options=[
                                                {"label": "All Years", "value": "all"},
                                                {"label": "2018", "value": "2018"},
                                                {"label": "2017", "value": "2017"},
                                                {"label": "2016", "value": "2016"},
                                                {"label": "2015", "value": "2015"},
                                                {"label": "2014", "value": "2014"},
                                                {"label": "2013", "value": "2013"},
                                                {"label": "2012", "value": "2012"},
                                            ],
                                            multi=False,
                                            clearable=False,
                                            id="years",
                                            value="2018",
                                        ),
                                    ],
                                    className="column is-3",
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(
                                            id="summary_graph",
                                            figure={
                                                "layout": {
                                                    "xaxis": {"visible": False},
                                                    "yaxis": {"visible": False},
                                                    "paper_bgcolor": "rgba(0,0,0,0)",
                                                    "plot_bgcolor": "rgba(0,0,0,0)",
                                                }
                                            },
                                            config={"displayModeBar": False},
                                        )
                                    ],
                                    className="column",
                                ),
                            ],
                            className="columns",
                        ),
                        html.H4("References", className="title is-4"),
                        html.Div(
                            [dcc.Markdown(TEXT["references"])], className="container"
                        ),
                        html.Br(),
                        html.Footer(
                            dcc.Markdown(TEXT["disclaimer"]), className="footer"
                        ),
                    ],
                    className="column",
                )
            ],
            className="columns",
        )
    ],
    className="section",
    style={"font-family": "Open Sans"},
)

app.layout = layout


@app.callback(
    Output("summary_graph", "figure"),
    [
        Input("campus", "value"),
        Input("job_titles", "value"),
        Input("pay_type", "value"),
        Input("years", "value"),
    ],
)
@cache.memoize()
def update_summary_graph(campus, job_titles, pay_type, years):
    if years == "all":
        return px.violin(
            UC_WIDE_SALARY_DF[UC_WIDE_SALARY_DF["Job Title"].isin(job_titles)],
            x="Year",
            y=pay_type,
            points=False,
            box=True,
        )
    elif years == "2018":
        fig = px.histogram(
            UC_WIDE_SALARY_DF[
                (UC_WIDE_SALARY_DF["Job Title"].isin(job_titles))
                & (UC_WIDE_SALARY_DF["Year"] == int(years))
            ],
            x=pay_type,
        )
        return fig
    else:
        raise PreventUpdate


@app.callback(
    Output("hud_graph", "figure"),
    [
        Input("campus", "value"),
        Input("discipline", "value"),
        Input("cost_of_living", "value"),
    ],
)
@cache.memoize()
def update_hud_graph(campus, discipline, cost_of_living):

    units = ["Efficiency", "1 br", "2 br", "3 br", "4 br"]

    # colors
    camp_colors = dict(zip(CAMPUSES, px.colors.qualitative.Bold))
    unit_colors = dict(
        zip(units, ["rgb({0}, {0}, {0})".format(str(50 + i * 50)) for i in range(5)])
    )
    ucop_survey_color = "rgb(255, 255, 51)"
    wage_color = "rgb(180, 151, 231)"

    years = [2007 + i for i in range(13)]
    unit_scaling = [1.0, 1.0, 1.0 / 2.0, 1.0 / 3.0, 1.0 / 4.0]
    label_prefix = ["", "", "Single in ", "Single in ", "Single in "]

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add traces for housing costs for each unit type
    min_y = 1e6  # for setting y axis range, arbitrary large value
    max_y = 0
    for i, unit in enumerate(units):
        unit_rent = HUD.loc[(campus, unit), "2007 FMR":"2019 FMR"].values.tolist()
        unit_rent = [rent * unit_scaling[i] for rent in unit_rent]
        min_y = min([min_y, *unit_rent])
        max_y = max([max_y, *unit_rent])
        fig.add_trace(
            go.Scatter(
                x=years,
                y=unit_rent,
                mode="lines+markers",
                name=label_prefix[i] + unit,
                line=dict(color=camp_colors[campus], width=5),
                marker=dict(
                    color=unit_colors[unit],
                    symbol=0,
                    size=10,
                    line=dict(color=camp_colors[campus], width=3),
                ),
            ),
            secondary_y=False,
        )

    # Add trace (single point) to show UCOP survey data
    fig.add_trace(
        go.Scatter(
            x=[2017],
            y=SURVEY.loc[campus].values.tolist(),
            mode="markers",
            name="UCOP Grad Survey Average",
            marker=dict(
                color=ucop_survey_color,
                symbol=17,
                size=15,
                line=dict(color=camp_colors[campus], width=3),
            ),
        ),
        secondary_y=False,
    )

    # Also plot mean/median wage vs time
    stipend_df = NET_STIPEND[
        (NET_STIPEND["Campus"] == campus) & (NET_STIPEND["Discipline"] == discipline)
    ]
    fig.add_trace(
        go.Scatter(
            # offset academic years to be ".5", e.g. 2016-2017 is 2016.5
            x=[y + 0.5 for y in stipend_df["Year"]],
            y=[s / 12 for s in stipend_df["Net Stipend"]],
            name="Net stipend",
            line=dict(color=wage_color, width=5),
            marker=dict(
                color=wage_color,
                symbol=0,
                size=10,
                line=dict(color=wage_color, width=3),
            ),
        ),
        secondary_y=True,
    )
    min_y = min([min_y, *[s / 12 for s in stipend_df["Net Stipend"]]])
    max_y = max([max_y, *[s / 12 for s in stipend_df["Net Stipend"]]])

    # Also plot rent burden threshold
    stipend_df = NET_STIPEND[
        (NET_STIPEND["Campus"] == campus) & (NET_STIPEND["Discipline"] == discipline)
    ]
    fig.add_trace(
        go.Scatter(
            # offset academic years to be ".5", e.g. 2016-2017 is 2016.5
            x=[y + 0.5 for y in stipend_df["Year"]],
            y=[(cost_of_living / 100) * s / 12 for s in stipend_df["Net Stipend"]],
            name="Rent burden threshold",
            mode="lines+markers",
            line=dict(color=wage_color, width=5),
            marker=dict(
                color="rgb(255, 255, 255)",
                symbol=0,
                size=10,
                line=dict(color=wage_color, width=3),
            ),
        ),
        secondary_y=True,
    )
    min_y = min(
        [min_y, *[(cost_of_living / 100) * s / 12 for s in stipend_df["Net Stipend"]]]
    )
    max_y = max(
        [max_y, *[(cost_of_living / 100) * s / 12 for s in stipend_df["Net Stipend"]]]
    )

    # Add figure title
    fig.update_layout(title_text=f"Housing costs and wages over time at UC {campus}")

    # Set x-axis title
    fig.update_xaxes(title_text="Year")

    # Set y-axes titles
    fig.update_yaxes(
        title_text="HUD Fair Market Rent - monthly ($)",
        title_font=dict(size=18, color=camp_colors[campus]),
        secondary_y=False,
        range=[min_y * 0.9, max_y * 1.1],
    )
    fig.update_yaxes(
        title_text="Net stipend - monthly ($)",
        title_font=dict(size=18, color=wage_color),
        secondary_y=True,
        showgrid=False,
        range=[min_y * 0.9, max_y * 1.1],
    )  # hide secondary axis grid

    # Move legend so it doesn't overlap secondary axis
    fig.update_layout(legend=dict(x=0, y=-0.2), legend_orientation="h")

    return fig


@app.callback(
    Output("deficit_graph", "figure"),
    [Input("campus", "value"), Input("cost_of_living", "value")],
)
@cache.memoize()
def update_deficit_graph(campus, cost_of_living_percent):

    stipend_df = NET_STIPEND[
        (NET_STIPEND["Campus"] == campus)
        & (NET_STIPEND["Discipline"] != "Other")
        & (NET_STIPEND["Discipline"] != "Joint/Unknown")
        & (
            NET_STIPEND["Discipline"] != "Professional"
        )  # no longer included in recent tables
    ]

    stipend_df["Cost-of-Living"] = stipend_df.apply(
        lambda row: get_cost_of_living(
            cost_of_living_percent, row["Campus"], row["Year"]
        ),
        axis=1,
    )

    stipend_df["Cost-of-Living Deficit ($/month)"] = stipend_df.apply(
        lambda row: row["Cost-of-Living"] - (row["Net Stipend"] / 12), axis=1
    )

    fig = px.scatter(
        stipend_df, x="Year", y="Cost-of-Living Deficit ($/month)", color="Discipline"
    )
    fig.update_traces(
        mode="markers+lines", marker=dict(symbol=0, size=10), line=dict(width=5)
    )

    # Add figure title
    fig.update_layout(
        title_text=f"Cost of living deficit by discipline at UC {campus} for a "
        f"{cost_of_living_percent}% rent burden threshold",
        legend=dict(x=0, y=-0.2),
        legend_orientation="h",
    )

    return fig


app.clientside_callback(
    """function (value) {
        return value;
    }
    """,
    Output("burden", "children"),
    [Input("cost_of_living", "value")],
)


@app.server.route("/uc-cola-whitepaper.pdf")
def download_csv():
    return flask.send_file(
        Path(__file__).parent.parent.absolute() / "whitepaper.pdf",
        mimetype="application/pdf",
        attachment_filename="uc-cola-whitepaper.pdf",
        as_attachment=True,
    )


if __name__ == "__main__":
    app.run_server(debug=True)
