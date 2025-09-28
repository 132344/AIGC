import React from 'react';
import { Bar, Line, Pie } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement, LineElement, ArcElement, Title, Tooltip, Legend } from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

const ChartDisplay = ({ chartType, chartData }) => {
  if (!chartType || !chartData) {
    return <p>无效的图表数据。</p>;
  }

  const data = {
    labels: chartData.map((_, index) => `数据点 ${index + 1}`), // 示例标签
    datasets: [
      {
        label: '数据',
        data: chartData,
        backgroundColor: [
          'rgba(255, 99, 132, 0.6)',
          'rgba(54, 162, 235, 0.6)',
          'rgba(255, 206, 86, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(153, 102, 255, 0.6)',
          'rgba(255, 159, 64, 0.6)',
        ],
        borderColor: [
          'rgba(255, 99, 132, 1)',
          'rgba(54, 162, 235, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(153, 102, 255, 1)',
          'rgba(255, 159, 64, 1)',
        ],
        borderWidth: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false, // Allow chart to fill its container
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: `${chartType}图`,
      },
    },
  };

  switch (chartType) {
    case '折线图':
      return <Line data={data} options={options} />;
    case '饼图':
      return <Pie data={data} options={options} />;
    case '柱状图':
      return <Bar data={data} options={options} />;
    default:
      return <p>不支持的图表类型: {chartType}</p>;
  }
};

export default ChartDisplay;
