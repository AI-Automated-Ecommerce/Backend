import re

def extract_images_from_tool_output(content):
    images = []
    lines = content.split('\n')
    for line in lines:
        if "Image:" in line:
            try:
                # Extract URL
                img_match = re.search(r'Image: (https?://[^\s]+)', line)
                if img_match:
                    img_url = img_match.group(1)
                    
                    # Extract Name and Price for caption
                    # "- Product Name (ID: 1): $19.99."
                    name_match = re.search(r'- (.*?) \(ID:', line)
                    name = name_match.group(1) if name_match else "Product"
                    
                    price_match = re.search(r'\$(\d+\.?\d*)', line)
                    price = float(price_match.group(1)) if price_match else 0.0
                    
                    stock_match = re.search(r'\[(.*?)\]', line)
                    stock_str = stock_match.group(1) if stock_match else ""
                    stock = 0
                    if "in stock" in stock_str:
                        stock_nums = re.findall(r'\d+', stock_str)
                        stock = int(stock_nums[0]) if stock_nums else 0

                    images.append({
                        "product_name": name,
                        "price": price,
                        "image_url": img_url,
                        "stock": stock
                    })
            except Exception as e:
                print(f"Error parsing product line: {e}")
    return images

def test_regex():
    print("Testing Regex Logic...")
    
    sample_output = """Found the following products:
- Red T-Shirt (ID: 101): $15.00. A nice red shirt. [10 in stock] Image: https://example.com/red-shirt.jpg
- Blue Jeans (ID: 102): $40.50. Comfortable jeans. [5 in stock] Image: https://example.com/blue-jeans.jpg
- Hat (ID: 5): $9.99. [Out of stock] Image: https://hats.com/hat.png
"""
    
    images = extract_images_from_tool_output(sample_output)
    
    print(f"Found {len(images)} images.")
    for img in images:
        print(f" - {img}")
        
    assert len(images) == 3
    assert images[0]['product_name'] == "Red T-Shirt"
    assert images[0]['stock'] == 10
    assert images[0]['price'] == 15.0
    
    assert images[1]['product_name'] == "Blue Jeans"
    assert images[1]['stock'] == 5
    
    assert images[2]['stock'] == 0
    
    print("\n✅ Regex Logic Verified!")

if __name__ == "__main__":
    test_regex()
