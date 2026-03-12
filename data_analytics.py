# data_analytics.py - Data Analytics Tab Functionality
from flask import render_template, jsonify, request
from datetime import datetime, timedelta
import calendar

def init_data_analytics_routes(app, execute_query):
    """Initialize all routes related to data analytics functionality"""
    
    @app.route('/visualization')
    def visualization():
        """Main data analytics/visualization page"""
        return render_template('visualization.html')

    @app.route('/api/dashboard_stats')
    def dashboard_stats():
        """Get overall dashboard statistics"""
        try:
            # Define all queries
            stats_queries = {
                'total_receipts': "SELECT COUNT(*) FROM receipts",
                'total_shopping_receipts': "SELECT COUNT(*) FROM receipts WHERE shopping_bill_no IS NOT NULL",
                'total_parking_receipts': "SELECT COUNT(*) FROM receipts WHERE parking_ticket_no IS NOT NULL",
                'total_revenue': "SELECT SUM(shopping_amount) FROM receipts WHERE shopping_amount IS NOT NULL",
                'avg_purchase': "SELECT AVG(shopping_amount) FROM receipts WHERE shopping_amount IS NOT NULL",
                'today_receipts': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE DATE(processed_at) = CURDATE()
                """,
                'this_week_receipts': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE YEARWEEK(processed_at) = YEARWEEK(CURDATE())
                """,
                'this_month_receipts': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE YEAR(processed_at) = YEAR(CURDATE()) 
                    AND MONTH(processed_at) = MONTH(CURDATE())
                """,
                'parking_validations': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE parking_validation_used = TRUE
                """,
                'fee_waivers': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE parking_fee_waived = TRUE
                """
            }
            
            stats = {}
            for key, query in stats_queries.items():
                try:
                    result = execute_query(query, fetch=True)
                    if result and result[0][0] is not None:
                        value = result[0][0]
                        # Convert Decimal to float for JSON serialization
                        if hasattr(value, '__float__'):
                            stats[key] = float(value)
                        else:
                            stats[key] = int(value) if isinstance(value, (int, float)) else value
                    else:
                        stats[key] = 0
                except Exception as e:
                    print(f"Error executing query for {key}: {e}")
                    stats[key] = 0
            
            # Calculate growth percentages (compared to last week/month)
            try:
                # Last week receipts
                last_week_query = """
                    SELECT COUNT(*) FROM receipts 
                    WHERE YEARWEEK(processed_at) = YEARWEEK(CURDATE()) - 1
                """
                last_week_result = execute_query(last_week_query, fetch=True)
                last_week_count = int(last_week_result[0][0]) if last_week_result and last_week_result[0][0] else 0
                
                if last_week_count > 0:
                    stats['week_growth'] = round(((stats['this_week_receipts'] - last_week_count) / last_week_count) * 100, 2)
                else:
                    stats['week_growth'] = 100 if stats['this_week_receipts'] > 0 else 0
                
                # Last month receipts
                last_month_query = """
                    SELECT COUNT(*) FROM receipts 
                    WHERE YEAR(processed_at) = YEAR(CURDATE() - INTERVAL 1 MONTH) 
                    AND MONTH(processed_at) = MONTH(CURDATE() - INTERVAL 1 MONTH)
                """
                last_month_result = execute_query(last_month_query, fetch=True)
                last_month_count = int(last_month_result[0][0]) if last_month_result and last_month_result[0][0] else 0
                
                if last_month_count > 0:
                    stats['month_growth'] = round(((stats['this_month_receipts'] - last_month_count) / last_month_count) * 100, 2)
                else:
                    stats['month_growth'] = 100 if stats['this_month_receipts'] > 0 else 0
                    
            except Exception as e:
                print(f"Error calculating growth stats: {e}")
                stats['week_growth'] = 0
                stats['month_growth'] = 0
            
            return jsonify(stats)
            
        except Exception as e:
            print(f"Error getting dashboard stats: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/shopping_stats')
    def shopping_stats():
        """Get shopping-related statistics and analytics"""
        try:
            # Daily trend for the last 30 days
            daily_trend_query = """
            SELECT 
                DATE(processed_at) as date,
                COUNT(*) as receipt_count,
                COALESCE(SUM(shopping_amount), 0) as total_amount,
                COALESCE(AVG(shopping_amount), 0) as avg_amount
            FROM receipts 
            WHERE shopping_amount IS NOT NULL 
            AND processed_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(processed_at)
            ORDER BY date DESC
            """
            
            daily_result = execute_query(daily_trend_query, fetch=True)
            daily_trend = []
            if daily_result:
                for row in daily_result:
                    date, count, total, avg = row
                    daily_trend.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'receipt_count': int(count),
                        'total_amount': float(total),
                        'avg_amount': float(avg)
                    })
            
            # Top stores by revenue
            top_stores_query = """
            SELECT 
                store_name,
                COUNT(*) as receipt_count,
                COALESCE(SUM(shopping_amount), 0) as total_revenue,
                COALESCE(AVG(shopping_amount), 0) as avg_amount
            FROM receipts 
            WHERE store_name IS NOT NULL 
            AND shopping_amount IS NOT NULL
            GROUP BY store_name
            ORDER BY total_revenue DESC
            LIMIT 10
            """
            
            stores_result = execute_query(top_stores_query, fetch=True)
            top_stores = []
            if stores_result:
                for row in stores_result:
                    store, count, revenue, avg = row
                    top_stores.append({
                        'store_name': store,
                        'receipt_count': int(count),
                        'total_revenue': float(revenue),
                        'avg_amount': float(avg)
                    })
            
            # Amount distribution
            amount_ranges_query = """
            SELECT 
                CASE 
                    WHEN shopping_amount < 500 THEN '0-499'
                    WHEN shopping_amount < 1000 THEN '500-999'
                    WHEN shopping_amount < 2000 THEN '1000-1999'
                    WHEN shopping_amount < 5000 THEN '2000-4999'
                    ELSE '5000+'
                END as amount_range,
                COUNT(*) as count
            FROM receipts 
            WHERE shopping_amount IS NOT NULL
            GROUP BY amount_range
            ORDER BY 
                CASE amount_range
                    WHEN '0-499' THEN 1
                    WHEN '500-999' THEN 2
                    WHEN '1000-1999' THEN 3
                    WHEN '2000-4999' THEN 4
                    ELSE 5
                END
            """
            
            ranges_result = execute_query(amount_ranges_query, fetch=True)
            amount_distribution = []
            if ranges_result:
                for row in ranges_result:
                    range_name, count = row
                    amount_distribution.append({
                        'range': range_name,
                        'count': int(count)
                    })
            
            # Hourly pattern
            hourly_pattern_query = """
            SELECT 
                HOUR(processed_at) as hour,
                COUNT(*) as receipt_count
            FROM receipts 
            WHERE shopping_amount IS NOT NULL
            AND processed_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY HOUR(processed_at)
            ORDER BY hour
            """
            
            hourly_result = execute_query(hourly_pattern_query, fetch=True)
            hourly_pattern = []
            if hourly_result:
                for row in hourly_result:
                    hour, count = row
                    hourly_pattern.append({
                        'hour': int(hour),
                        'count': int(count)
                    })
            
            return jsonify({
                'daily_trend': daily_trend,
                'top_stores': top_stores,
                'amount_distribution': amount_distribution,
                'hourly_pattern': hourly_pattern
            })
            
        except Exception as e:
            print(f"Error getting shopping stats: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/receipt_stats')
    def receipt_stats():
        """Get detailed receipt statistics"""
        try:
            # Monthly receipt trend
            monthly_query = """
            SELECT 
                YEAR(processed_at) as year,
                MONTH(processed_at) as month,
                COUNT(*) as total_receipts,
                COUNT(CASE WHEN shopping_amount IS NOT NULL THEN 1 END) as shopping_receipts,
                COUNT(CASE WHEN parking_ticket_no IS NOT NULL THEN 1 END) as parking_receipts,
                COALESCE(SUM(shopping_amount), 0) as total_revenue
            FROM receipts 
            WHERE processed_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY YEAR(processed_at), MONTH(processed_at)
            ORDER BY year DESC, month DESC
            """
            
            monthly_result = execute_query(monthly_query, fetch=True)
            monthly_stats = []
            if monthly_result:
                for row in monthly_result:
                    year, month, total, shopping, parking, revenue = row
                    month_name = calendar.month_name[month]
                    monthly_stats.append({
                        'year': int(year),
                        'month': int(month),
                        'month_name': month_name,
                        'total_receipts': int(total),
                        'shopping_receipts': int(shopping),
                        'parking_receipts': int(parking),
                        'total_revenue': float(revenue)
                    })
            
            # Status distribution
            status_query = """
            SELECT 
                status,
                COUNT(*) as count
            FROM receipts 
            GROUP BY status
            """
            
            status_result = execute_query(status_query, fetch=True)
            status_distribution = []
            if status_result:
                for row in status_result:
                    status, count = row
                    status_distribution.append({
                        'status': status,
                        'count': int(count)
                    })
            
            # Processing success rate
            success_rate_query = """
            SELECT 
                COUNT(CASE WHEN shopping_amount IS NOT NULL OR parking_ticket_no IS NOT NULL THEN 1 END) as successful,
                COUNT(*) as total
            FROM receipts
            """
            
            success_result = execute_query(success_rate_query, fetch=True)
            success_rate = 0
            if success_result and success_result[0][1] > 0:
                successful, total = success_result[0]
                success_rate = round((successful / total) * 100, 2)
            
            return jsonify({
                'monthly_stats': monthly_stats,
                'status_distribution': status_distribution,
                'success_rate': success_rate
            })
            
        except Exception as e:
            print(f"Error getting receipt stats: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/recent_receipts')
    def recent_receipts():
        """Get recent receipts for dashboard"""
        try:
            query = """
            SELECT 
                id, store_name, shopping_bill_no, shopping_amount, 
                shopping_date, processed_at, status,
                parking_ticket_no, vehicle_no, parking_fee_waived
            FROM receipts 
            ORDER BY processed_at DESC
            LIMIT 10
            """
            
            result = execute_query(query, fetch=True)
            recent_receipts = []
            
            if result:
                for row in result:
                    receipt_id, store, bill_no, amount, shop_date, processed, status, \
                    parking_ticket, vehicle, fee_waived = row
                    
                    recent_receipts.append({
                        'id': receipt_id,
                        'store_name': store or 'Unknown',
                        'bill_number': bill_no or parking_ticket or 'N/A',
                        'amount': float(amount) if amount else 0,
                        'date': shop_date.strftime('%d/%m/%Y %H:%M') if shop_date else 'N/A',
                        'processed_at': processed.strftime('%d/%m/%Y %H:%M') if processed else 'N/A',
                        'status': status or 'unknown',
                        'type': 'shopping' if amount else 'parking',
                        'vehicle_number': vehicle,
                        'parking_fee_waived': bool(fee_waived)
                    })
            
            return jsonify({'recent_receipts': recent_receipts})
            
        except Exception as e:
            print(f"Error getting recent receipts: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/test')
    def test_page():
        """Test page for debugging"""
        try:
            # Test database connection
            test_query = "SELECT COUNT(*) as total_receipts FROM receipts"
            result = execute_query(test_query, fetch=True)
            
            if result:
                total_receipts = result[0][0]
                return jsonify({
                    'status': 'success',
                    'message': 'Database connection working',
                    'total_receipts': int(total_receipts)
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to query database'
                })
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Database test failed: {str(e)}'
            })

    # Additional analytics helper functions
    def get_peak_hours():
        """Get peak shopping hours"""
        query = """
        SELECT 
            HOUR(processed_at) as hour,
            COUNT(*) as receipt_count
        FROM receipts 
        WHERE shopping_amount IS NOT NULL
        GROUP BY HOUR(processed_at)
        ORDER BY receipt_count DESC
        LIMIT 5
        """
        return execute_query(query, fetch=True)

    def get_seasonal_trends():
        """Get seasonal shopping trends"""
        query = """
        SELECT 
            MONTH(processed_at) as month,
            COUNT(*) as receipt_count,
            AVG(shopping_amount) as avg_amount
        FROM receipts 
        WHERE shopping_amount IS NOT NULL
        AND processed_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        GROUP BY MONTH(processed_at)
        ORDER BY month
        """
        return execute_query(query, fetch=True)

    def get_customer_patterns():
        """Get customer shopping patterns"""
        query = """
        SELECT 
            phone_number,
            COUNT(*) as visit_count,
            AVG(shopping_amount) as avg_spend,
            MAX(processed_at) as last_visit
        FROM receipts 
        WHERE phone_number IS NOT NULL 
        AND shopping_amount IS NOT NULL
        GROUP BY phone_number
        HAVING visit_count > 1
        ORDER BY visit_count DESC, avg_spend DESC
        LIMIT 20
        """
        return execute_query(query, fetch=True)

    return app
