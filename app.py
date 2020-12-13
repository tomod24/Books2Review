import os
from datetime import datetime
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import pymongo
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


@app.route('/file/<filename>')
def file(filename):
   return mongo.send_file(filename)


@app.route("/get_tasks")
def get_tasks():
    tasks = list(mongo.db.tasks.find())
    return render_template("tasks.html", tasks=tasks)

@app.route("/book_review_edit/<review_id>", methods=["GET", "POST"])
def book_review_edit(review_id):
    # check if review is in system
    review = mongo.db.reviews.find_one({'_id': ObjectId(review_id)})
    review["user_id"] == session['user'] or session['user'] == 'admin'
    if review is None:
        flash("It looks like that review has been removed.")
        return redirect(url_for("get_books"))
    book = mongo.db.books.find_one({'_id': ObjectId(review['book_id'])})
    if session.get("user"):
        if session.get("user") == review["user_id"]:
            if request.method == "POST":
                review = {
                    "book_id": review['book_id'],
                    "islike": request.form.get("islike"),
                    "comment": request.form.get("comment"),
                    "user_id": session["user"],
                    "create_date": datetime.now()
                }
                mongo.db.reviews.update({"_id": ObjectId(review_id)}, review)
                flash("Review Successfully Updated")
                return redirect(url_for("book_detail", book_id=review['book_id']))
            else:
                return render_template("book_review_edit.html", review=review, book=book)
        else:
            flash("Only the user that created the review can update the review.")
            return redirect(url_for("book_detail", book_id=review["book_id"]))
    flash("You Must Login To Update A Review")
    return redirect(url_for("login"))


@app.route("/")
@app.route("/get_books")
def get_books():
    books = list(mongo.db.books.find())
    return render_template("get_books.html", books=books)


@app.route("/book_detail/<book_id>", methods=["GET"])
def book_detail(book_id):
    book = mongo.db.books.find_one({'_id': ObjectId(book_id)})
    reviews = list(mongo.db.reviews.find({'book_id': book_id}, {
                   'create_date': 1, 'comment': 1, 'user_id': 1, 'islike': 1}).sort('create_date', pymongo.DESCENDING).limit(3))
    total_ups = mongo.db.reviews.find(
        {'book_id': book_id, 'islike': 'on'}).count()
    total_downs = mongo.db.reviews.find(
        {'book_id': book_id, 'islike': {'$type': 10}}).count()
    total_reviews = mongo.db.reviews.find({'book_id': book_id}).count()
    return render_template("book_detail.html", book=book, reviews=reviews, total_ups=total_ups, total_downs=total_downs, total_reviews=total_reviews)



@app.route("/search", methods=["GET", "POST"])
def search():
    query = request.form.get("query")
    books = list(mongo.db.books.find({"$text": {"$search": query}}))
    return render_template("get_books.html", books=books)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # check if username already exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        if existing_user:
            flash("Username already exists")
            return redirect(url_for("register"))

        register = {
            "username": request.form.get("username").lower(),
            "password": generate_password_hash(request.form.get("password"))
        }
        mongo.db.users.insert_one(register)

        # put the new user into 'session' cookie
        session["user"] = request.form.get("username").lower()
        flash("Registration Successful!")
        return redirect(url_for("profile", username=session["user"]))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # check if username exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        if existing_user:
            # ensure hashed password matches user input
            if check_password_hash(
                    existing_user["password"], request.form.get("password")):
                session["user"] = request.form.get("username").lower()
                flash("Welcome, {}".format(
                    request.form.get("username")))
                return redirect(url_for(
                    "profile", username=session["user"]))
            else:
                # invalid password match
                flash("Incorrect Username and/or Password")
                return redirect(url_for("login"))

        else:
            # username doesn't exist
            flash("Incorrect Username and/or Password")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    # grab the session user's username from db
    username = mongo.db.users.find_one(
        {"username": session["user"]})["username"]
    if session["user"]:
        books = []
        if session["user"] =="admin":
            reviews = list(mongo.db.reviews.find({}))
        else:
            reviews = list(mongo.db.reviews.find({'user_id': session['user']}))
        if username == "admin":
            books = list(mongo.db.books.find({'created_by': 'admin'}))
        return render_template("profile.html", username=username, reviews=reviews, books=books)
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    # remove user from session cookie
    flash("You have been logged out")
    session.pop("user")
    return redirect(url_for("login"))


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if session.get("user"):
        if session["user"] == "admin":
            if request.method == "POST" and 'book_cover' in request.files:
                book = {
                    "title": request.form.get("book_title"),
                    "author": request.form.get("book_author"),
                    "genre": request.form.get("book_genre"),
                    "year": request.form.get("book_year"),
                    "description": request.form.get("book_description"),
                    "created_by": session["user"]
                }
                new_book = mongo.db.books.insert_one(book)
                cover_image = request.files['book_cover']
                # have unique filename based on id of newly added book
                mongo.save_file(str(new_book.inserted_id) + "_" +
                                cover_image.filename, cover_image)
                mongo.db.books.update_one(
                    {'_id': new_book.inserted_id},
                    {
                        '$set': {'book_cover': str(new_book.inserted_id) + "_" + cover_image.filename}
                    }
                )
                return redirect(url_for("get_books"))
            else:
                return render_template("add_book.html")
        else:
             flash("Only the admin can add books")
             return redirect(url_for("get_books"))
    else:
            flash("You must be logged in as admin to add a book.")
            return redirect(url_for("login"))


@app.route("/edit_task/<task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if request.method == "POST":
        is_urgent = "on" if request.form.get("is_urgent") else "off"
        submit = {
            "category_name": request.form.get("category_name"),
            "task_name": request.form.get("task_name"),
            "task_description": request.form.get("task_description"),
            "is_urgent": is_urgent,
            "due_date": request.form.get("due_date"),
            "created_by": session["user"]
        }
        mongo.db.tasks.update({"_id": ObjectId(task_id)}, submit)
        flash("Task Successfully Updated")

    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    categories = mongo.db.categories.find().sort("category_name", 1)
    return render_template("edit_task.html", task=task, categories=categories)

@app.route("/delete_review/<review_id>")
def delete_review(review_id):
    mongo.db.reviews.delete_one({"_id": ObjectId(review_id)})
    flash("Review Successfully Deleted")
    return redirect(url_for("get_books"))


@app.route("/get_categories")
def get_categories():
    categories = list(mongo.db.categories.find().sort("category_name", 1))
    return render_template("categories.html", categories=categories)


@app.route("/add_category", methods=["GET", "POST"])
def add_category():
    if request.method == "POST":
        category = {
            "category_name": request.form.get("category_name")
        }
        mongo.db.categories.insert_one(category)
        flash("New Category Added")
        return redirect(url_for("get_categories"))

    return render_template("add_category.html")


@app.route("/edit_category/<category_id>", methods=["GET", "POST"])
def edit_category(category_id):
    if request.method == "POST":
        submit = {
            "category_name": request.form.get("category_name")
        }
        mongo.db.categories.update({"_id": ObjectId(category_id)}, submit)
        flash("Category Successfully Updated")
        return redirect(url_for("get_categories"))

    category = mongo.db.categories.find_one({"_id": ObjectId(category_id)})
    return render_template("edit_category.html", category=category)


@app.route("/delete_category/<category_id>")
def delete_category(category_id):
    mongo.db.categories.remove({"_id": ObjectId(category_id)})
    flash("Category Successfully Deleted")
    return redirect(url_for("get_categories"))


@app.route("/add_review/<book_id>", methods=["GET", "POST"])
def add_review(book_id):
    if session.get("user"):
        if request.method == "POST":
            review = {
                "book_id": book_id,
                "islike": request.form.get("islike"),
                "comment": request.form.get("comment"),
                "user_id": session["user"],
                "create_date": datetime.now()
            }
            mongo.db.reviews.insert_one(review)
            flash("Review Successfully Added")
            book = mongo.db.books.find_one({'_id': ObjectId(book_id)})
            return redirect(url_for("book_detail", book_id=book_id))
        else:
            book = mongo.db.books.find_one({'_id': ObjectId(book_id)})
            return render_template("add_review.html", book=book)
    flash("You Must Login To Add A Review")
    return redirect(url_for("login"))

@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404
@app.errorhandler(500)
def error_page_not_found(e):
    # note that we set the 500 status explicitly
    return render_template('500.html'), 500


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
