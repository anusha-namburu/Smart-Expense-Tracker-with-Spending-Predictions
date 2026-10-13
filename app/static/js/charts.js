// Smart Expense Tracker - Chart.js Initializers

// Global Default Font & Color Styling for Chart.js
if (window.Chart) {
  Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  Chart.defaults.color = '#64748b';
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

/**
 * Initializes all Dashboard Visualizations by querying the JSON API
 */
async function initDashboardCharts() {
  try {
    const res = await fetch('/dashboard/charts-api');
    if (!res.ok) return;
    const data = await res.json();

    // 1. Category Doughnut Chart
    const catCanvas = document.getElementById('categoryDoughnutChart');
    if (catCanvas && data.category_chart.labels.length > 0) {
      new Chart(catCanvas, {
        type: 'doughnut',
        data: {
          labels: data.category_chart.labels,
          datasets: [{
            data: data.category_chart.data,
            backgroundColor: data.category_chart.colors,
            borderWidth: 2,
            borderColor: '#ffffff',
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { boxWidth: 12, padding: 15 }
            },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.label}: $${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
              }
            }
          },
          cutout: '68%'
        }
      });
    }

    // 2. Daily Spending Trend Line Chart
    const dailyCanvas = document.getElementById('dailyTrendChart');
    if (dailyCanvas) {
      new Chart(dailyCanvas, {
        type: 'line',
        data: {
          labels: data.daily_chart.labels,
          datasets: [{
            label: 'Daily Expenses ($)',
            data: data.daily_chart.data,
            borderColor: '#4361ee',
            backgroundColor: 'rgba(67, 97, 238, 0.08)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 3,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              ticks: { callback: (val) => `$${val}` }
            },
            x: {
              grid: { display: false }
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => ` Spent: $${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
              }
            }
          }
        }
      });
    }

    // 3. Monthly Income vs Expenses Bar Chart
    const monthlyCanvas = document.getElementById('monthlyComparisonChart');
    if (monthlyCanvas) {
      new Chart(monthlyCanvas, {
        type: 'bar',
        data: {
          labels: data.monthly_chart.labels,
          datasets: [
            {
              label: 'Income',
              data: data.monthly_chart.income,
              backgroundColor: '#10b981',
              borderRadius: 6
            },
            {
              label: 'Expenses',
              data: data.monthly_chart.expense,
              backgroundColor: '#ef4444',
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              ticks: { callback: (val) => `$${val}` }
            },
            x: {
              grid: { display: false }
            }
          },
          plugins: {
            legend: { position: 'top' },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.dataset.label}: $${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
              }
            }
          }
        }
      });
    }

    // 4. Budget vs Actual Grouped Bar Chart
    const budgetCanvas = document.getElementById('budgetVsActualChart');
    if (budgetCanvas && data.budget_chart.labels.length > 0) {
      new Chart(budgetCanvas, {
        type: 'bar',
        data: {
          labels: data.budget_chart.labels,
          datasets: [
            {
              label: 'Budget Limit',
              data: data.budget_chart.limits,
              backgroundColor: '#94a3b8',
              borderRadius: 6
            },
            {
              label: 'Actual Spent',
              data: data.budget_chart.actuals,
              backgroundColor: '#4361ee',
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              ticks: { callback: (val) => `$${val}` }
            },
            x: {
              grid: { display: false }
            }
          },
          plugins: {
            legend: { position: 'top' },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.dataset.label}: $${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
              }
            }
          }
        }
      });
    }
  } catch (err) {
    console.error('Error rendering dashboard charts:', err);
  }
}

/**
 * Initializes the ML Spending Forecast Timeline Chart
 */
function initForecastTimelineChart(timeline, budgetLimit) {
  const canvas = document.getElementById('forecastTimelineChart');
  if (!canvas || !timeline || timeline.length === 0) return;

  const labels = timeline.map(item => `Day ${item.day}`);
  const actuals = timeline.map(item => item.type === 'actual' ? item.amount : null);
  const forecasts = timeline.map(item => item.type === 'forecast' ? item.amount : null);

  // Connect last actual point to first forecast point for visual continuity
  const lastActualIdx = actuals.findLastIndex(val => val !== null);
  if (lastActualIdx !== -1 && lastActualIdx < forecasts.length - 1) {
    forecasts[lastActualIdx] = actuals[lastActualIdx];
  }

  const datasets = [
    {
      label: 'Actual Daily Spend ($)',
      data: actuals,
      borderColor: '#4361ee',
      backgroundColor: 'rgba(67, 97, 238, 0.1)',
      borderWidth: 2.5,
      tension: 0.3,
      fill: false,
      pointRadius: 4,
      pointBackgroundColor: '#4361ee'
    },
    {
      label: 'Predicted Daily Spend ($)',
      data: forecasts,
      borderColor: '#8b5cf6',
      borderDash: [6, 6],
      backgroundColor: 'rgba(139, 92, 246, 0.1)',
      borderWidth: 2.5,
      tension: 0.3,
      fill: false,
      pointRadius: 4,
      pointBackgroundColor: '#8b5cf6'
    }
  ];

  new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: '#f1f5f9' },
          ticks: { callback: (val) => `$${val}` }
        },
        x: { grid: { display: false } }
      },
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: $${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
          }
        }
      }
    }
  });
}
