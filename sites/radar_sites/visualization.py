"""Shared conventions for HRRR-AK simulations and field observations."""
SIMULATION_COLORS = {'hrrrak': 'maroon', 'hrrrak_lapserate': 'royalblue'}
SIMULATION_LABELS = {'hrrrak': 'HRRR-AK Raw', 'hrrrak_lapserate': 'HRRR-AK Lapserate'}
SIMULATION_LINEWIDTH = 2.2
ADJUSTED_LINEWIDTH = 2.2
OBSERVATION_COLOR = 'black'
OBSERVATION_MARKERS = {'pit': 'o', 'radar': 's'}
RC_PARAMS = {
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 13,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 12,
    'axes.spines.top': False,
    'axes.spines.right': False,
}


def comparison_legend(fig, handles, columns=3, bottom=.10):
    """Reserve space below all panels for a shared figure legend."""
    fig.subplots_adjust(bottom=bottom, hspace=.30, wspace=.22)
    return fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5,.015),
                      ncol=columns, frameon=False)
