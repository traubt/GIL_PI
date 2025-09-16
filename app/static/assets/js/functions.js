function dialog(dialog_title, dialog_body) {
  // Set the title of the modal
  $('#exampleModalLabel').text(dialog_title);

  // Set the body content of the modal
  $('#dialog_body').html(dialog_body);

  // Show the modal directly without triggering the button click
  $('#exampleModal').modal('show');
}

    // Get the current date in yyyy-mm-dd format
    // 2/3/25 - add hours minutes
function getCurrentDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = (today.getMonth() + 1).toString().padStart(2, '0'); // Add leading zero if needed
    const day = today.getDate().toString().padStart(2, '0'); // Add leading zero if needed
    const hours = today.getHours().toString().padStart(2, '0'); // Add leading zero
    const minutes = today.getMinutes().toString().padStart(2, '0'); // Add leading zero
    return `${year}${month}${day}${hours}${minutes}`;
}

function allOrderQtyZero() {
    return $('#ProductOrderTemplate').DataTable().column(8).data().toArray().every(value => value === 0)
}

async function fetchTOCShops() {
    try {
        const response = await fetch('/api/toc_shops'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json(); // Parse JSON response
        _shops = data; // Populate _shops with the fetched data
        console.log(_shops); // Log the updated _shops variable to the console
    } catch (error) {
        console.error('Error fetching TOC Shops:', error);
    }
}

// Fetch all products
async function fetchProducts() {
    try {
        const response = await fetch('/api/products'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const products = await response.json(); // Parse JSON response
        _products = products;
        console.log(_products); // Log the product data to the console
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

// Fetch all products
async function fetchOpenOrders() {
    try {
        const response = await fetch('/api/open_orders'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        _open_orders = await response.json(); // Parse JSON response
        console.log(_open_orders);
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

function getShopCodeByBlName(blName) {
    const shop = _shops.find(item => item.blName === blName);
    return shop ? shop.customer : null; // Return the customer or null if not found
}

function getShopNameByCode(code) {
    const shop = _shops.find(item => item.customer === code);
    return shop ? shop.blName : null; // Return the customer or null if not found
}

// Function to extract shop code and retrieve the shop name
function getShopNameFromOrderId(orderID) {
    // Extract the shop code from the orderID (first part before the '_')
    const shopCode = orderID.split('_')[0];

    // Use the helper function to get the shop name
    const shopName = getShopNameByCode(shopCode);

    return shopName; // Return the shop name (or null if not found)
}

// disable controls
function disableControlsPerRole(roles,userRole){
    // Pass the roles data from Flask to JavaScript as a JSON string

  console.log("Roles:", roles, userRole);

  var exclusions = "";  // To hold the exclusions list

  // Find the exclusions list for the current user's role
  roles.forEach(function(role) {
    if (role.role === userRole) {
      exclusions = role.exclusions;
    }
  });

  // If exclusions exist, disable the elements with corresponding IDs
  if (exclusions) {
    // Split the exclusions string by commas and loop through each exclusion
    var excludedIds = exclusions.split(',');

    excludedIds.forEach(function(id) {
      // Disable the element with the corresponding ID
      var element = $('#' + id);
      element.prop('disabled', true);  // This won't work for non-form elements

      // Add a 'disabled' class and make the item non-clickable
      element.css({
        'opacity': '0.5',  // Dim the item to indicate it's disabled
        'pointer-events': 'none',  // Disable any click interaction
      });

      // Optionally, you can also change the cursor to indicate it's not clickable
      element.css('cursor', 'not-allowed');

      console.log('Disabled element:', id);
    });
  }

};


async function logUserActivity(activityDescription) {
    try {
        const response = await fetch('/log_user_activity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ activity: activityDescription })
        });

        if (response.ok) {
            const data = await response.json();
            console.log("Activity logged successfully:", data);
        } else {
            const errorData = await response.json();
            console.error("Error logging activity:", errorData);
        }
    } catch (error) {
        console.error("Network error:", error);
    }
}

// Helper function to format date as yyyy-mm-dd
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatDate2(date) {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function f_num(num){
    return new Intl.NumberFormat('en-US').format(num);
}

function f_num1(num){
    num = num.toFixed(1)
    return new Intl.NumberFormat('en-US').format(num);
}

///////   Create dynamic Datatable function
async function setupDynamicTable(buttonId, tableId, apiEndpoint, refIdx) {
    // Remove any previous click event listeners to avoid duplication
    $(`#${buttonId}`).off("click").on("click", async function (event) {
        try {
            // Check if DataTable exists, then destroy it
            if ($.fn.DataTable.isDataTable(`#${tableId}`)) {
                $(`#${tableId}`).DataTable().clear().destroy();
            }

            // Fetch data from the API endpoint
            const response = await fetch(apiEndpoint);
            const result = await response.json();

            // Ensure columns and rows exist in the response
            if (result.columns && result.rows) {
                const columns = result.columns.map((col, index) => {
                    // Add rendering logic for the 3rd column (index 2)
                    if (index === refIdx) {
                        return {
                            title: col,
                            render: function (data, type, row) {
                                return `<a href="#" onclick="alert('Clicked: ${data}')">${data}</a>`;
                            }
                        };
                    }
                    return { title: col };
                });

                // Initialize DataTable
                $(`#${tableId}`).DataTable({
                    data: result.rows, // Use rows from the API
                    columns: columns, // Use dynamic columns
                    autoWidth: true,
                    order: [], // Default ordering
                    stripeClasses: ["table-row-even", "table-row-odd"] // Define custom classes for striped rows
                });
            } else {
                dialog("Error", "Invalid response structure from the server", BootstrapDialog.TYPE_INFO);
            }
        } catch (e) {
            dialog("Error", `Can't fetch data: ${e.message}`, BootstrapDialog.TYPE_INFO);
        }
    });
}


/// create a pie chart dynamic
  // Function to create the ECharts pie chart
  function createPieChart(topItems) {
    const chartDom = document.getElementById('pie-chart');
    const myChart = echarts.init(chartDom);

    const option = {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c} ({d}%)'
      },
      legend: {
        show: false  // Hide default legend
      },
      series: [
        {
          name: 'Top Spenders',
          type: 'pie',
          radius: '50%',
          label: {
            formatter: '{b}: {d}%',  // Custom label with percentage
            show: true
          },
          data: topItems,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    };

    // Set chart options
    myChart.setOption(option);
  }

    // Function to create the ECharts bar chart
  function createBarChart(labels, values) {
    const chartDom = document.getElementById('bar-chart');
    const myChart = echarts.init(chartDom);

    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: '{b}: {c} ({d}%)'
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: {
          rotate: 45,
          interval: 0
        }
      },
      yAxis: {
        type: 'value'
      },
      series: [
        {
          name: 'Total Spent',
          type: 'bar',
          data: values,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    };

    myChart.setOption(option);
  }

    // Function to generate chart options dynamically
function generateChartOptions(type, result,title, yAxis) {
  // Sort rows by 'total_spent' (index 2) in descending order
  const sortedData = result.rows.sort((a, b) => b[2] - a[2]);

  // Limit to top 10 spenders
  const top10Data = sortedData.slice(0, 10);

  if (type === 'pie') {
    // Prepare data for the pie chart
    const pieData = top10Data.map(row => ({
      name: row[0],     // Customer name
      value: row[2]     // Total spent
    }));

    // Return pie chart options
    return {
      title: {
        text: title,
        left: 'center'
      },
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)'
      },
//      legend: {
//        orient: 'vertical',
//        left: 'left'
//      },
      series: [
        {
          name: yAxis,
          type: 'pie',
          radius: '50%',
          data: pieData,  // Use the formatted pie data
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    };

  } else if (type === 'bar') {
    // Prepare data for the bar chart
    const barData = top10Data.map(row => ({
      name: row[0],     // Customer name
      value: row[2]     // Total spent
    }));

    // Return bar chart options
    return {
      title: {
        text: title,
        left: 'center'
      },
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c}'
      },
      xAxis: {
        type: 'category',
        data: barData.map(item => item.name),  // Customer names on x-axis
        axisLabel: {
          rotate: 45  // Rotate labels for better visibility
        }
      },
      yAxis: {
        type: 'value',
        name: 'Total Spent',
        axisLabel: {
          formatter: '{value}'
        }
      },
      series: [
        {
          name: yAxis,
          type: 'bar',
          data: barData.map(item => item.value),  // Total spent on y-axis
          itemStyle: {
            color: '#007bff'  // Optional: Color for bars
          }
        }
      ]
    };
  }

  // Return empty object if type is not recognized
  return {};
}


function fetchLastUpdateTime() {
    fetch('/get_last_update') // Call the Flask route
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json(); // Parse the response as JSON
        })
        .then(data => {
            if (data.success) {
                //console.log('Last update:', data.last_update_time); // Log the result
                // You can update the UI with the fetched time here
                document.getElementById('lastUpdate').textContent = `Last update: ${data.last_update_time}`;
            } else {
                console.error('Error fetching last update:', data.error); // Log the error
            }
        })
        .catch(error => {
            console.error('Fetch error:', error); // Handle fetch errors
        });
}

/**
 * Create a notification
 * @param {string} toUser  - recipient username or user_id
 * @param {string} subject - notification subject
 * @param {string} body    - notification body
 */
async function createNotification(toUser, subject, body) {
    const now = new Date();
    const data = {
        not_date: now.toISOString().slice(0, 19).replace("T", " "), // ✅ MySQL DATETIME
        not_address: toUser,           // in GIL PI -> user instead of shop
        not_subject: subject,
        not_body: body,
        not_status: "unread"
    };

    try {
        const response = await fetch('/create_notification', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const res = await response.json();
        if (response.ok) {
            console.log("✅ Notification created:", res);
            return true;
        } else {
            console.error("⚠️ Error creating notification:", res);
            return false;
        }
    } catch (error) {
        console.error("💥 Fetch error in createNotification:", error);
        return false;
    }
}







